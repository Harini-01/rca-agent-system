# Core agent loop
import json
from rca_agent.llm_client import GeminiClient
from utils.command_executor import run_command


class RCAAgent:
    def __init__(self):
        self.llm = GeminiClient()
        self.max_steps = 5

    def analyze(self, anomaly_description):
        context = f"Anomaly detected: {anomaly_description}\n"
        
        for step in range(self.max_steps):
            prompt = self._build_prompt(context)

            response = self.llm.generate(prompt)

            if "error" in response:
                return response

            output = response["response"]

            print(f"\n[LLM Step {step+1}]:\n{output}")

            # Try to parse JSON action
            action = self._parse_action(output)

            if action["type"] == "final":
                return action["content"]

            elif action["type"] == "command":
                cmd_output = run_command(action["content"])
                context += f"\nCommand: {action['content']}\nOutput:\n{cmd_output}\n"

        return "Failed to determine root cause within step limit."

#     def _build_prompt(self, context):
    def _build_prompt(self, context):
        return f"""
You are a system troubleshooting expert.

You are working on a WINDOWS system.

Use Windows commands like:
- tasklist (for processes)
- wmic cpu get loadpercentage
- systeminfo

Respond ONLY in JSON format:

If you want to run a command:
{{ "type": "command", "content": "your_command_here" }}

If you know the root cause:
{{ "type": "final", "content": "your root cause explanation" }}

Context:
{context}
"""

    def _parse_action(self, output):
        try:
            return json.loads(output)
        except:
            return {"type": "final", "content": output}