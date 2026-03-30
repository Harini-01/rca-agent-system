# Low-level safe execution
import subprocess
import shlex

# Optional: define allowed commands for safety
ALLOWED_COMMANDS = {
    "ps",
    "top",
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