import time
import subprocess
from collections import deque

from detector.anomaly_detector import predict_anomaly
from rca_agent.agent import RCAAgent
from detector.log_watcher import stream_syslog


# ================================
# ⚙️ CONFIG (TUNE THESE)
# ================================
CPU_THRESHOLD = 85        # %
MEM_THRESHOLD = 80        # %
DISK_THRESHOLD = 80       # %

ML_CONF_THRESHOLD = 0.6   # confidence of predicted class

TRIGGER_LIMIT = 1         # how many consecutive anomalies before RCA
DECAY = 1                 # score decay when normal


# ================================
# 📊 METRICS COLLECTION
# ================================
def get_metrics():
    """
    Collect system metrics using vmstat + iostat
    Must match training feature order exactly
    """

    try:
        vm = subprocess.getoutput("vmstat 1 2").splitlines()[-1].split()

        mem_swap = float(vm[2])
        mem_free = float(vm[3])
        mem_buffer = float(vm[4])
        mem_cache = float(vm[5])

        cpu_user = float(vm[12])
        cpu_system = float(vm[13])
        cpu_idle = float(vm[14])
        cpu_iowait = float(vm[15])

    except:
        cpu_user = cpu_system = cpu_idle = cpu_iowait = 0
        mem_free = mem_buffer = mem_cache = mem_swap = 0

    try:
        io = subprocess.getoutput("iostat -x 1 1").splitlines()
        disk_line = io[-1].split()

        disk_read_s = float(disk_line[3])
        disk_write_s = float(disk_line[4])
        disk_read_kb = float(disk_line[5])
        disk_write_kb = float(disk_line[6])
        disk_await = float(disk_line[9])
        disk_util = float(disk_line[-1])

    except:
        disk_read_s = disk_write_s = disk_read_kb = disk_write_kb = 0
        disk_await = disk_util = 0

    return [
        cpu_user, cpu_system, cpu_idle, cpu_iowait,
        mem_free, mem_buffer, mem_cache, mem_swap,
        disk_read_s, disk_read_kb, disk_write_s, disk_write_kb,
        disk_await, disk_util
    ]


# ================================
# 🧠 RULE-BASED DETECTION
# ================================
def rule_based_detection(metrics):
    cpu_user = metrics[0]
    cpu_system = metrics[1]
    cpu_usage = cpu_user + cpu_system

    mem_free = metrics[4]
    mem_buffer = metrics[5]
    mem_cache = metrics[6]

    # Approx memory usage (heuristic)
    mem_used_percent = 100 - (mem_free / (mem_free + mem_buffer + mem_cache + 1e-6)) * 100

    disk_util = metrics[-1]

    cpu_flag = cpu_usage > CPU_THRESHOLD
    mem_flag = mem_used_percent > MEM_THRESHOLD
    disk_flag = disk_util > DISK_THRESHOLD

    return cpu_flag, mem_flag, disk_flag


# ================================
# 🤖 ML-BASED DETECTION
# ================================
def ml_detection(metrics, logs):
    pred, proba = predict_anomaly(metrics, logs)

    confidence = proba[pred]

    ml_flag = (pred != 0) and (confidence > ML_CONF_THRESHOLD)

    return ml_flag, pred, confidence


# ================================
# 🚀 MAIN LOOP
# ================================
def main_loop():
    print("🚀 RCA System (Hybrid Mode) Started...\n")

    agent = RCAAgent()

    log_buffer = deque(maxlen=5)
    anomaly_score = 0

    # 🔥 NEW: Cooldown config
    COOLDOWN = 30  # seconds
    last_rca_time = 0

    for log_line in stream_syslog():
        print(f"\n📥 New log: {log_line}")

        log_buffer.append(log_line)
        logs = "\n".join(log_buffer)

        metrics = get_metrics()

        print("🧠 Running anomaly detection...")

        # ===== Rule-based =====
        cpu_flag, mem_flag, disk_flag = rule_based_detection(metrics)

        # ===== ML-based =====
        ml_flag, pred, confidence = ml_detection(metrics, logs)

        print(f"Prediction: {pred}, Confidence: {confidence:.2f}")
        print(f"Rule Flags → CPU: {cpu_flag}, MEM: {mem_flag}, DISK: {disk_flag}, ML: {ml_flag}")

        # ===== Hybrid decision =====
        anomaly_detected = cpu_flag or mem_flag or disk_flag or ml_flag

        # 🔥 OPTIONAL (for demo reliability)
        # Uncomment this if system is not triggering reliably
        # anomaly_detected = True

        # ===== Score update (with decay) =====
        if anomaly_detected:
            anomaly_score += 1
        else:
            anomaly_score = max(0, anomaly_score - DECAY)

        print(f"📊 Anomaly score: {anomaly_score}")

        # ===== Trigger RCA with cooldown =====
        current_time = time.time()

        if (
            anomaly_score >= TRIGGER_LIMIT
            and (current_time - last_rca_time) > COOLDOWN
        ):
            print("\n⚠️ CONSISTENT ANOMALY DETECTED → Running RCA...\n")

            last_rca_time = current_time  # 🔥 update cooldown timer

            anomaly_context = f"""
System anomaly detected.

Recent Logs:
{logs}

Metrics Snapshot:
CPU Usage: {metrics[0] + metrics[1]}%
CPU Idle: {metrics[2]}%
Memory Free: {metrics[4]}
Disk Utilization: {metrics[-1]}%

Note: High CPU usage detected from system metrics.
"""

            result = agent.analyze(anomaly_context)

            print("\n==============================")
            print("🧠 RCA RESULT")
            print("==============================")
            print(result)
            print("==============================\n")

            # Reset after RCA (important)
            anomaly_score = 0
# ================================
# 🔌 LLM TEST
# ================================
# def test_llm():
#     from rca_agent.llm_client import OllamaClient

#     print("\n[TEST] Checking Ollama connection...")
#     client = OllamaClient()

#     response = client.generate("Say hello")

#     if "error" in response:
#         print("❌ Ollama not working:", response["error"])
#         return False

#     print("✅ Ollama Working\n")
#     return True


def run_demo(log_text, demo_metrics=None):
    agent = RCAAgent()

    logs = log_text

    # 🔥 KEY CHANGE
    if demo_metrics:
        metrics = demo_metrics
    else:
        metrics = get_metrics()

    cpu_flag, mem_flag, disk_flag = rule_based_detection(metrics)
    ml_flag, pred, confidence = ml_detection(metrics, logs)

    anomaly_detected = cpu_flag or mem_flag or disk_flag or ml_flag

    if anomaly_detected:
        anomaly_context = f"""
System anomaly detected.

Logs:
{logs}

Metrics:
CPU User: {metrics[0]}%
CPU System: {metrics[1]}%
Memory Free: {metrics[4]}
Disk Utilization: {metrics[-1]}%
"""

        result = agent.analyze(anomaly_context)

        return {
            "prediction": int(pred),
            "confidence": float(confidence),
            "metrics": metrics,
            "result": result
        }

    return {
        "prediction": int(pred),
        "confidence": float(confidence),
        "metrics": metrics,
        "result": "No anomaly detected"
    }

if __name__ == "__main__":
    main_loop()