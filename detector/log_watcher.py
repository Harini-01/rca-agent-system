# Log watcher
import subprocess

def stream_syslog():
    """Continuously yield new syslog lines."""
    
    process = subprocess.Popen(
        ["tail", "-F", "/var/log/syslog"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    while True:
        line = process.stdout.readline()
        if not line:
            continue
        yield line.strip()