# Entry point for RCA Agent System

import os
from dotenv import load_dotenv

from rca_agent.llm_client import GeminiClient
from rca_agent.agent import RCAAgent


def check_api():
    """Ensure Gemini API key is set."""
    if not os.getenv("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY not set!")
        print("Add it to .env file like: GEMINI_API_KEY=your-api-key")
        return False
    return True


def test_llm():
    """Quick test to verify Gemini is working."""
    print("\n[TEST] Checking Gemini connection...")

    client = GeminiClient()

    response = client.generate(
        prompt="Explain CPU usage in simple terms."
    )

    if "error" in response:
        print(f"❌ LLM Error: {response['error']}")
        return False

    print("✅ LLM Working\n")
    return True


def run_agent():
    """Run RCA Agent."""
    print("\n🚀 Starting RCA Agent...\n")

    agent = RCAAgent()

    anomaly = "System is slow and CPU usage is high"

    print(f"🔍 Analyzing anomaly: {anomaly}\n")

    result = agent.analyze(anomaly)

    print("\n==============================")
    print("🧠 FINAL ROOT CAUSE ANALYSIS")
    print("==============================")
    print(result)
    print("==============================\n")


if __name__ == "__main__":
    load_dotenv()

    # Step 1: Check API
    if not check_api():
        exit(1)

    # Step 2: Test LLM
    if not test_llm():
        exit(1)

    # Step 3: Run Agent
    run_agent()