# # Core agent loop
# import json
# import re
# from utils.command_executor import run_command
# from rca_agent.llm_client import OllamaClient
# from rca_agent.llm_client import GeminiClient
# from rca_agent.llm_client import FreeLLMClient


# class RCAAgent:
#     def __init__(self):
#         # self.llm = OllamaClient()
#         # self.llm = GeminiClient()
#         self.llm = FreeLLMClient()
#         self.max_steps = 10

#     def analyze(self, anomaly_description):
#         context = f"Anomaly: {anomaly_description}\n"
#         commands_run = 0
#         command_history = []  # Keep track of recent commands
        
#         for step in range(self.max_steps):
#             print(f"[DEBUG] Step {step+1} | Commands run: {commands_run}")

#             prompt = self._build_prompt(context, commands_run)
#             # response = self.llm.generate(prompt)
#             try:
#                 response = self.llm.generate(prompt)
#             except:
#                 return "LLM timeout - RCA could not complete"

#             if "error" in response:
#                 return response

#             output = response["response"]
#             print(f"\n[LLM Step {step+1}]:\n{output}")

#             # Parse JSON action
#             action = self._parse_action(output)

#             if action["type"] == "invalid":
#                 print("⚠️ Invalid JSON, retrying...")
#                 continue

#             if action["type"] == "text":
#                 # Intermediate reasoning - add to context and continue
#                 context += f"\n[LLM Analysis]: {action['content']}\n"
#                 continue

#             if action["type"] == "final":
#                 print(f"[DEBUG] Final requested with commands_run={commands_run}")

#                 if commands_run < 2:
#                     print(f"⚠️ Must run at least 2 commands before final (only ran {commands_run}), retrying...")
#                     context += "\n[System]: You must run at least 2 diagnostic commands before giving final answer.\n"
#                     continue

#                 return action["content"]

#             elif action["type"] == "command":
#                 cmd_output = run_command(action["content"])

#                 # Only count successful executions
#                 if cmd_output.get("return_code") == 0:
#                     commands_run += 1
#                     print(f"[DEBUG] Commands executed so far: {commands_run}")
#                 else:
#                     print(f"[WARNING] Command failed with return_code={cmd_output.get('return_code')}")

#                 # Make output VERY prominent so LLM can use it
#                 output_section = f"""
# ================== COMMAND {commands_run} OUTPUT ==================
# Command: {action['content']}
# Result:
# {str(cmd_output)}
# ====================================================================
# """
#                 print(output_section)

#                 # Add to command history (keep last 3 commands only)
#                 command_history.append(output_section)
#                 if len(command_history) > 3:
#                     command_history.pop(0)

#                 # Rebuild context with anomaly + recent commands
#                 context = f"Anomaly: {anomaly_description}\n" + "\n".join(command_history)

#         return "Failed to determine root cause within step limit."

#     def _parse_action(self, output):
#         try:
#             action = json.loads(output.strip())
#             if "type" not in action or "content" not in action:
#                 return {"type": "invalid"}
#             return action
#         except json.JSONDecodeError:
#             return {"type": "invalid"}

#     def _build_prompt(self, context, commands_run=0):
#         status = f"Commands executed so far: {commands_run}"
        
#         if commands_run == 0:
#             requirement = "REQUIRED: You MUST run at least 2 commands before using 'final' type."
#         elif commands_run == 1:
#             requirement = "REQUIRED: Run at least 1 more command before using 'final' type."
#         else:
#             requirement = "You may now use 'final' type if you have identified the root cause."
        
#         return f"""Anomaly: {context}

# {status}
# {requirement}

# IMPORTANT: Above this line, you can see the actual command outputs in === COMMAND X OUTPUT === sections.
# YOU MUST STRICTLY USE ONLY THIS DATA.

# OUTPUT EXACTLY ONE JSON OBJECT. DO NOT OUTPUT ARRAYS OR MULTIPLE OBJECTS.

# AVAILABLE COMMANDS - Choose ONE from this list EACH TIME:

# {{"type":"command","content":"top -bn1 | head -10"}}

# {{"type":"command","content":"ps aux --sort=-%cpu | head -15"}}

# {{"type":"command","content":"free -m"}}

# {{"type":"command","content":"vmstat 1 2"}}

# {{"type":"command","content":"iostat 1 1"}}

# AFTER running commands, analyze what you see:

# {{"type":"text","content":"Analysis: Based ONLY on the command output, I observe..."}}

# WHEN you have enough data, provide final answer:

# {{"type":"final","content":"Root Cause: [process name] (PID XXXX) using XX% CPU. Recommendation: [action]."}}

# STRICT RULES (MUST FOLLOW):

# 1. You MUST ONLY use information present in COMMAND OUTPUT sections.
# 2. If process name, PID, or CPU% is NOT visible → DO NOT mention it.
# 3. DO NOT guess, assume, or hallucinate any values.
# 4. DO NOT reuse examples like 'yes' or 'watchdog' unless they appear in output.
# 5. DO NOT repeat the same command twice.
# 6. You MUST run at least 2 DIFFERENT commands before "final".
# 7. If data is insufficient → DO NOT give final.

# IF INSUFFICIENT DATA:
# Return EXACTLY:
# {{"type":"text","content":"Insufficient data, running another command"}}

# FINAL OUTPUT MUST INCLUDE:
# - exact process name FROM OUTPUT
# - exact PID FROM OUTPUT
# - exact CPU or memory value FROM OUTPUT

# FAILURE TO FOLLOW RULES = INVALID RESPONSE
# """
import json
import re
from utils.command_executor import run_command
from rca_agent.llm_client import FreeLLMClient


class RCAAgent:
    def __init__(self):
        self.llm = FreeLLMClient()
        self.max_steps = 12
        self.max_failures = 3

    # =========================
    # MAIN LOOP (STABLE VERSION)
    # =========================
    def analyze(self, anomaly_description):

        context = (
            "Anomaly:\n"
            f"{anomaly_description.strip()}\n\n"
            "If you do not have exact PID and process evidence, do not return final. Run another command.\n"
        )
        command_history = []
        executed = set()

        commands_run = 0
        failures = 0
        no_progress_steps = 0

        for step in range(self.max_steps):
            print(f"\n[DEBUG] Step {step+1} | Commands run: {commands_run}")

            prompt = self._build_prompt(context, commands_run)

            try:
                response = self.llm.generate(prompt)
            except Exception as e:
                return f"LLM crash: {str(e)}"

            if not response or "error" in response:
                return response

            output = response.get("response", "").strip()
            print(f"\n[LLM OUTPUT]\n{output}")

            actions = self._extract_json_objects(output)
            if not actions:
                failures += 1
                print("⚠️ No valid JSON")
                if failures >= self.max_failures:
                    return "RCA failed: invalid LLM outputs"
                context += "\n[system]: Could not parse JSON action. Reply only with one JSON object.\n"
                continue

            failures = 0
            action = actions[0]
            progress_made = False

            if action["type"] in {"text", "analysis"}:
                analysis_text = str(action["content"]).strip()
                context += f"\n[analysis]: {analysis_text}\n"
                progress_made = True

            elif action["type"] == "final":
                if commands_run < 2:
                    context += "\n[system]: Run at least two different diagnostic commands before final.\n"
                else:
                    if self._validate_final(action["content"], command_history):
                        return self._final_to_string(action["content"])
                    print("⚠️ Final answer rejected: missing evidence or required fields")
                    context += (
                        "\n[system]: Final answer must include actual PID, process name, reason, evidence, "
                        "and recommendation from the command outputs.\n"
                    )

            elif action["type"] == "command":
                cmd = str(action["content"]).strip()
                if not cmd:
                    context += "\n[system]: Command content was empty. Provide one valid command.\n"
                elif cmd in executed:
                    context += "\n[system]: Command already executed. Choose a new command.\n"
                else:
                    executed.add(cmd)
                    print(f"\n🚀 EXECUTING: {cmd}")
                    cmd_output = run_command(cmd)
                    commands_run += 1
                    progress_made = True
                    if cmd_output.get("return_code") != 0:
                        print("⚠️ Command failed")
                    block = self._format_command_output(commands_run, cmd, cmd_output)
                    print(f"\n{block}\n")
                    command_history.append(block)
                    command_history = command_history[-4:]
                    context = (
                        f"Anomaly:\n{anomaly_description.strip()}\n\n"
                        + "\n".join(command_history)
                    )

            if progress_made:
                no_progress_steps = 0
            else:
                no_progress_steps += 1

            if no_progress_steps >= 3:
                context += "\n[system]: You are stuck. Choose a new diagnostic command or summarize exact evidence.\n"
                no_progress_steps = 0

        return "RCA failed: max steps reached"

    # =========================
    # SAFE JSON EXTRACTION
    # =========================
    def _extract_json_objects(self, text):
        decoder = json.JSONDecoder()
        results = []
        idx = 0

        while True:
            idx = text.find("{", idx)
            if idx == -1:
                break
            try:
                obj, end = decoder.raw_decode(text[idx:])
                if isinstance(obj, dict) and "type" in obj and "content" in obj:
                    results.append(obj)
                idx += end
            except ValueError:
                idx += 1
                continue

        # Fallback: Try to extract final answer from truncated JSON
        if not results and "final" in text:
            results.extend(self._parse_truncated_final(text))

        return results

    def _parse_truncated_final(self, text):
        """Fallback parser for truncated final JSON responses."""
        import re
        results = []

        # Try to extract process, pid, reason from truncated final response
        pid_match = re.search(r'"pid"\s*:\s*["\']*(\d{2,6})', text)
        process_match = re.search(r'"process"\s*:\s*"([^"]{1,50})"', text)
        reason_match = re.search(r'"reason"\s*:\s*"([^"]{1,100})"', text)
        recommendation_match = re.search(r'"recommendation"\s*:\s*"([^"]{1,100})"', text)

        if pid_match and process_match:
            obj = {
                "type": "final",
                "content": {
                    "pid": pid_match.group(1),
                    "process": process_match.group(1),
                    "reason": reason_match.group(1) if reason_match else "Unknown",
                    "evidence": "Evidence not fully captured",
                    "recommendation": recommendation_match.group(1) if recommendation_match else "Review process"
                }
            }
            results.append(obj)

        return results

    def _format_command_output(self, index, command, cmd_output):
        stdout = cmd_output.get("stdout", "").strip()
        stderr = cmd_output.get("stderr", "").strip()
        return (
            f"=== COMMAND OUTPUT {index} ===\n"
            f"COMMAND: {command}\n"
            f"RETURN_CODE: {cmd_output.get('return_code')}\n"
            "STDOUT:\n"
            f"{stdout}\n"
            "STDERR:\n"
            f"{stderr}\n"
            "========================="
        )

    def _validate_final(self, content, command_history):
        history_text = "\n".join(command_history)

        if isinstance(content, dict):
            pid = str(content.get("pid", "")).strip()
            process = str(content.get("process", "")).strip()
            if not pid or not process:
                return False
            if not re.search(r"\b" + re.escape(pid) + r"\b", history_text):
                return False
            if process not in history_text:
                return False
            return True

        if isinstance(content, str):
            pid_match = re.search(r"\bPID[: ]*(\d{2,6})\b", content, re.I)
            process_match = re.search(r"\bprocess[: ]*([A-Za-z0-9_\-/.]+)\b", content, re.I)
            if not pid_match or not process_match:
                return False
            pid = pid_match.group(1)
            process = process_match.group(1)
            if not re.search(r"\b" + re.escape(pid) + r"\b", history_text):
                return False
            if process not in history_text:
                return False
            return True

        return False

    def _final_to_string(self, content):
        if isinstance(content, dict):
            return (
                f"\n📌 PROCESS: {content.get('process')} (PID {content.get('pid')})\n"
                f"🔍 REASON: {content.get('reason', 'Unknown')}\n"
                f"✅ EVIDENCE: {content.get('evidence', 'Evidence not provided')}\n"
                f"⚡ ACTION: {content.get('recommendation', 'No recommendation provided')}\n"
            )
        return str(content)

    # =========================
    # PROMPT (ANTI-HALLUCINATION + ANTI-STUCK)
    # =========================
    def _build_prompt(self, context, commands_run):

        return f"""
You are a SYSTEM DEBUGGING AGENT.

TASK:
- Identify the single process causing the anomaly.
- Provide exact PID, exact process name, a concise reason, evidence from the command output, and a recommendation.
- If the evidence is insufficient, run another command.
- Do not guess or hallucinate.

RULES:
- Output ONLY ONE JSON object per response.
- Do not output any text outside the JSON object.
- Do not repeat the same command.
- Do not use fake PID or process names.
- EVIDENCE field must be concise: ONE LINE ONLY, max 80 characters. Example: "yes process using 94.7% CPU"
- Do NOT include full command output in evidence. Just cite the key line.
- If you cannot confirm the offending process with exact evidence, do not use type "final".

STATE:
commands_run = {commands_run}

OUTPUT FORMAT ONLY:

{{"type":"command","content":"<single command>"}}
{{"type":"analysis","content":"observation"}}
{{"type":"final","content":{{"process":"<process>","pid":"<pid>","reason":"<reason>","evidence":"<one-line max 80 chars>","recommendation":"<recommendation>"}}}}

EVIDENCE EXAMPLES (keep concise, one line):
- "yes process using 94.7% CPU (PID 8940)"
- "python main.py consuming 7.5 GB memory"
- "sshd process listening on 0.0.0.0:22"

AVAILABLE COMMANDS:
ps aux --sort=-%cpu | head -15
ps aux --sort=-%mem | head -15
top -bn1 | head -20
ps -eo pid,ppid,pcpu,pmem,comm --sort=-pcpu | head -15
free -m
df -h
vmstat 1 2
iostat -x 1 1
cat /proc/<pid>/cmdline
lsof -p <pid>
journalctl -n 50 --no-pager
ss -tunp | head -20

CONTEXT:
{context}"""
