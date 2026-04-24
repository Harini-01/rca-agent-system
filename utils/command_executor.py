# Low-level safe execution
import subprocess
import shlex

# Optional: define allowed commands for safety
ALLOWED_COMMANDS = {
    "ps",
    "top",
    "htop",
    "free",
    "vmstat",
    "iostat",
    "dmesg",
    "journalctl",
    "grep",
    "cat",
    "awk",
    "sed",
    "head",
    "tail"
}

def run_command(command: str, timeout: int = 5) -> dict:
    """
    Executes a shell command safely and returns structured output.
    """

    try:
        # Split command into tokens
        parts = shlex.split(command)

        if not parts:
            return {"error": "Empty command"}

        base_cmd = parts[0]

        # Safety check
        if base_cmd not in ALLOWED_COMMANDS:
            return {
                "error": f"Command '{base_cmd}' is not allowed."
            }

        # Execute command
        result = subprocess.run(
            parts,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        return {
            "command": command,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "return_code": result.returncode
        }

    except subprocess.TimeoutExpired:
        return {
            "error": "Command timed out"
        }

    except Exception as e:
        return {
            "error": str(e)
        }


# def run_command(cmd):
#     # 🔥 DEMO MODE
#     if "ps aux" in cmd:
#         return {
#             "return_code": 0,
#             "stdout": """
# USER   PID %CPU %MEM COMMAND
# root  2345 99.5  0.1 yes
# root  1111  2.0  0.5 systemd
# """,
#             "stderr": ""
#         }

#     if "top" in cmd:
#         return {
#             "return_code": 0,
#             "stdout": """
# %Cpu(s): 95.0 us, 5.0 sy
# PID USER %CPU COMMAND
# 2345 root 99.5 yes
# """,
#             "stderr": ""
#         }

#     if "free -m" in cmd:
#         return {
#             "return_code": 0,
#             "stdout": """
# Mem: 8000 total, 7800 used, 200 free
# """,
#             "stderr": ""
#         }

#     if "iostat" in cmd:
#         return {
#             "return_code": 0,
#             "stdout": """
# Device: sda %util 92.0
# """,
#             "stderr": ""
#         }

#     return {
#         "return_code": 1,
#         "stdout": "",
#         "stderr": "Command not allowed"
#     }