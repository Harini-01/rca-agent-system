# Core agent loop
import json
import re
from utils.command_executor import run_command
from rca_agent.llm_client import OllamaClient


class RCAAgent:
    def __init__(self):
        self.llm = OllamaClient()
        self.max_steps = 10

    def analyze(self, anomaly_description):
        context = f"Anomaly: {anomaly_description}\n"
        commands_run = 0
        command_history = []  # Keep track of recent commands
        
        for step in range(self.max_steps):
            print(f"[DEBUG] Step {step+1} | Commands run: {commands_run}")

            prompt = self._build_prompt(context, commands_run)
            response = self.llm.generate(prompt)

            if "error" in response:
                return response

            output = response["response"]
            print(f"\n[LLM Step {step+1}]:\n{output}")

            # Parse JSON action
            action = self._parse_action(output)

            if action["type"] == "invalid":
                print("⚠️ Invalid JSON, retrying...")
                continue

            if action["type"] == "text":
                # Intermediate reasoning - add to context and continue
                context += f"\n[LLM Analysis]: {action['content']}\n"
                continue

            if action["type"] == "final":
                print(f"[DEBUG] Final requested with commands_run={commands_run}")

                if commands_run < 2:
                    print(f"⚠️ Must run at least 2 commands before final (only ran {commands_run}), retrying...")
                    context += "\n[System]: You must run at least 2 diagnostic commands before giving final answer.\n"
                    continue

                return action["content"]

            elif action["type"] == "command":
                cmd_output = run_command(action["content"])

                # Only count successful executions
                if cmd_output.get("return_code") == 0:
                    commands_run += 1
                    print(f"[DEBUG] Commands executed so far: {commands_run}")
                else:
                    print(f"[WARNING] Command failed with return_code={cmd_output.get('return_code')}")

                # Make output VERY prominent so LLM can use it
                output_section = f"""
================== COMMAND {commands_run} OUTPUT ==================
Command: {action['content']}
Result:
{str(cmd_output)}
====================================================================
"""
                print(output_section)

                # Add to command history (keep last 3 commands only)
                command_history.append(output_section)
                if len(command_history) > 3:
                    command_history.pop(0)

                # Rebuild context with anomaly + recent commands
                context = f"Anomaly: {anomaly_description}\n" + "\n".join(command_history)

        return "Failed to determine root cause within step limit."

    def _build_prompt(self, context, commands_run=0):
        status = f"Commands executed so far: {commands_run}"
        
        if commands_run == 0:
            requirement = "REQUIRED: You MUST run at least 2 commands before using 'final' type."
        elif commands_run == 1:
            requirement = "REQUIRED: Run at least 1 more command before using 'final' type."
        else:
            requirement = "You may now use 'final' type if you have identified the root cause."
        
        return f"""Anomaly: {context}

{status}
{requirement}

IMPORTANT: Above this line, you can see the actual command outputs in === COMMAND X OUTPUT === sections.
ANALYZE THE REAL DATA YOU SEE, NOT MADE-UP DATA.

OUTPUT EXACTLY ONE JSON OBJECT. DO NOT OUTPUT ARRAYS OR MULTIPLE OBJECTS.

AVAILABLE COMMANDS - Choose ONE from this list EACH TIME:

{{"type":"command","content":"top -bn1 | head -20"}}

{{"type":"command","content":"ps aux --sort=-%cpu | head -15"}}

{{"type":"command","content":"free -m"}}

{{"type":"command","content":"vmstat 1 2"}}

{{"type":"command","content":"iostat 1 1"}}

AFTER running commands, analyze what you see:

{{"type":"text","content":"Analysis: Based on the top output above, I see process X using Y% CPU with Z MB memory..."}}

WHEN you have enough data, provide final answer:

{{"type":"final","content":"Root Cause: Found process 'yes' (PID 1234) at 100% CPU causing slowness. Recommendation: kill the process."}}

RULES:
- Copy ONE command exactly from the list - do NOT modify
- Always reference ACTUAL data you see in the COMMAND OUTPUT sections above
- Never make up process names or numbers
- "text" type: summarize what the command outputs show
- "final" type: ONLY after 2+ commands with specific process name, PID, and CPU%
"""

    def _parse_action(self, output):
        try:
            # Reject if output contains array syntax
            if output.strip().startswith("["):
                return {"type": "invalid", "content": "Array output not allowed"}

            # Priority: extract final type
            final_match = re.search(
                r'\{"[^"]*type"[^"]*:\s*"final"[^}]*"content"[^}]*\}',
                output,
                re.DOTALL
            )
            if final_match:
                try:
                    action = json.loads(final_match.group(0))
                    if "content" in action and action["content"] and action["content"].strip():
                        return action
                except:
                    pass

            # Secondary: generic JSON object
            match = re.search(
                r'\{[^{}]*"type"\s*:\s*"[^"]*"[^{}]*"content"\s*:[^}]*\}',
                output,
                re.DOTALL
            )

            if match:
                try:
                    action = json.loads(match.group(0))
                    if "type" in action and "content" in action:
                        if not action["content"] or (
                            isinstance(action["content"], str) and action["content"].strip() == ""
                        ):
                            return {"type": "invalid", "content": "Empty content"}
                        return action
                except:
                    pass

            # Fallback: brute JSON extraction
            start = output.find("{")
            if start >= 0:
                brace_count = 0
                for i in range(start, len(output)):
                    if output[i] == "{":
                        brace_count += 1
                    elif output[i] == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            json_str = output[start:i+1]
                            try:
                                action = json.loads(json_str)
                                if "type" in action and "content" in action:
                                    if not action["content"] or (
                                        isinstance(action["content"], str) and action["content"].strip() == ""
                                    ):
                                        return {"type": "invalid", "content": "Empty content"}
                                    return action
                            except:
                                pass

            return {"type": "invalid", "content": "Could not parse valid JSON"}

        except Exception:
            return {"type": "invalid", "content": "Parsing exception"}