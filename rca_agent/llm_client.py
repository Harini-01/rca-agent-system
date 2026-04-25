# Interface with Ollama (local LLM)
import requests


class OllamaClient:
    def __init__(self, model="phi3"):
        """Initialize Ollama client."""
        self.model = model
        self.url = "http://localhost:11434/api/generate"

    def generate(self, prompt, system_prompt=None):
        """Generate response from Ollama."""
        try:
            # Combine system + user prompt (same behavior as Gemini)
            if system_prompt:
                full_prompt = f"{system_prompt}\n\nUser: {prompt}"
            else:
                full_prompt = prompt

            response = requests.post(
                self.url,
                json={
                    "model": self.model,
                    "prompt": full_prompt,
                    "stream": False
                },
                timeout=180
            )

            if response.status_code != 200:
                return {
                    "error": f"Ollama API error: {response.text}",
                    "status": "error"
                }

            result = response.json()

            return {
                "response": result.get("response", ""),
                "status": "success"
            }

        except requests.exceptions.ConnectionError:
            return {
                "error": "Could not connect to Ollama. Is it running?",
                "status": "error"
            }
        except Exception as e:
            return {
                "error": f"Generation failed: {str(e)}",
                "status": "error"
            }

    def test_connection(self):
        """Test if Ollama is running."""
        try:
            response = requests.get("http://localhost:11434")
            if response.status_code == 200:
                return {
                    "status": "connected",
                    "message": f"Ollama is running (model: {self.model})"
                }
            else:
                return {
                    "status": "disconnected",
                    "message": "Ollama server not responding"
                }
        except Exception as e:
            return {
                "status": "disconnected",
                "message": f"Connection failed: {str(e)}"
            }

    def list_available_models(self):
        """List locally available models."""
        try:
            response = requests.get("http://localhost:11434/api/tags")
            models = [m["name"] for m in response.json().get("models", [])]

            return {
                "status": "success",
                "models": models
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }


from google import genai

class GeminiClient:
    def __init__(self):
        self.client = genai.Client(api_key="AIzaSyD-UCrRJncPs0-PSFB1bK_Dnytw1iKWDPs")

    def generate(self, prompt):
        try:
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )

            text = response.text.strip()

            # 🔥 Remove markdown if Gemini adds it
            if text.startswith("```"):
                text = text.split("```")[1]

            return {"response": text}

        except Exception as e:
            return {"error": str(e)}


from ollamafreeapi import OllamaFreeAPI

class FreeLLMClient:
    def __init__(self):
        self.client = OllamaFreeAPI()

    def generate(self, prompt):
        try:
            response = self.client.chat(
                model="gpt-oss:20b",
                prompt=prompt
            )

            return {
                "response": response
            }

        except Exception as e:
            return {
                "error": str(e)
            }