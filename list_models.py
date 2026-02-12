import os

from dotenv import load_dotenv
from google import genai

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("❌ GEMINI_API_KEY not found")
    exit(1)

try:
    client = genai.Client(api_key=api_key)
    print("✅ Client initialized. Fetching models...")

    # Try different ways to list models depending on SDK version
    try:
        # Standard way for google.genai
        models = client.models.list()
        print("\nAvailable Models:")
        for m in models:
            print(f"- {m.name}")
            if "flash" in m.name:
                print(f"  (Candidate: {m.name})")
    except Exception as e:
        print(f"Error listing models: {e}")

except Exception as e:
    print(f"❌ Error: {e}")
