# Core agent loop
import json
import re
from utils.command_executor import run_command
from rca_agent.llm_client import OllamaClient
from rca_agent.llm_client import GeminiClient


class RCAAgent:
    def __init__(self):
        # self.llm = OllamaClient()
        self.llm = GeminiClient()
        self.max_steps = 5

    def analyze(self, anomaly_description):
        context = f"Anomaly: {anomaly_description}\n"
        commands_run = 0
        command_history = []  # Keep track of recent commands
        
        for step in range(self.max_steps):
            print(f"[DEBUG] Step {step+1} | Commands run: {commands_run}")

            prompt = self._build_prompt(context, commands_run)
            # response = self.llm.generate(prompt)
            try:
                response = self.llm.generate(prompt)
            except:
                return "LLM timeout - RCA could not complete"

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
YOU MUST STRICTLY USE ONLY THIS DATA.

OUTPUT EXACTLY ONE JSON OBJECT. DO NOT OUTPUT ARRAYS OR MULTIPLE OBJECTS.

AVAILABLE COMMANDS - Choose ONE from this list EACH TIME:

{{"type":"command","content":"top -bn1 | head -10"}}

{{"type":"command","content":"ps aux --sort=-%cpu | head -15"}}

{{"type":"command","content":"free -m"}}

{{"type":"command","content":"vmstat 1 2"}}

{{"type":"command","content":"iostat 1 1"}}

AFTER running commands, analyze what you see:

{{"type":"text","content":"Analysis: Based ONLY on the command output, I observe..."}}

WHEN you have enough data, provide final answer:

{{"type":"final","content":"Root Cause: [process name] (PID XXXX) using XX% CPU. Recommendation: [action]."}}

STRICT RULES (MUST FOLLOW):

1. You MUST ONLY use information present in COMMAND OUTPUT sections.
2. If process name, PID, or CPU% is NOT visible → DO NOT mention it.
3. DO NOT guess, assume, or hallucinate any values.
4. DO NOT reuse examples like 'yes' or 'watchdog' unless they appear in output.
5. DO NOT repeat the same command twice.
6. You MUST run at least 2 DIFFERENT commands before "final".
7. If data is insufficient → DO NOT give final.

IF INSUFFICIENT DATA:
Return EXACTLY:
{{"type":"text","content":"Insufficient data, running another command"}}

FINAL OUTPUT MUST INCLUDE:
- exact process name FROM OUTPUT
- exact PID FROM OUTPUT
- exact CPU or memory value FROM OUTPUT

FAILURE TO FOLLOW RULES = INVALID RESPONSE
"""