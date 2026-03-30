# Interface with Gemini API
import os
from google import genai

class GeminiClient:
    def __init__(self, model="gemini-2.5-flash"):
        """Initialize Gemini client with API key from environment."""
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")
        
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def generate(self, prompt, system_prompt=None):
        """Generate response from Gemini."""
        try:
            # Combine system and user prompts
            if system_prompt:
                full_prompt = f"{system_prompt}\n\nUser: {prompt}"
            else:
                full_prompt = prompt

            # Generate content
            response = self.client.models.generate_content(
                model=self.model,
                contents=full_prompt
            )

            return {
                "response": response.text,
                "status": "success"
            }

        except ValueError as e:
            return {"error": f"Invalid request: {str(e)}", "status": "error"}
        except Exception as e:
            return {"error": f"Generation failed: {str(e)}", "status": "error"}

    def test_connection(self):
        """Test if Gemini API is accessible."""
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents="Hello"
            )
            return {
                "status": "connected",
                "message": f"Successfully connected to {self.model}"
            }
        except Exception as e:
            return {
                "status": "disconnected",
                "message": f"Connection failed: {str(e)}"
            }

    def list_available_models(self):
        """List all available models."""
        try:
            models_list = self.client.models.list()
            models = [model.name for model in models_list]
            return {"status": "success", "models": models}
        except Exception as e:
            return {"status": "error", "message": str(e)}