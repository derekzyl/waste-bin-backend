#!/usr/bin/env python3
"""
Quick diagnostic script to test Gemini API integration
"""

import os
import sys

# Add backend directory to path
sys.path.insert(0, "/home/cybergenii/Desktop/codes/embedded/smart-waste-bin/backend")

from dotenv import load_dotenv

# Load environment
load_dotenv()

print("=" * 60)
print("GEMINI API DIAGNOSTIC")
print("=" * 60)

# Check API key
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    print(f"✅ GEMINI_API_KEY found: {api_key[:15]}...")
else:
    print("❌ GEMINI_API_KEY not found in environment")
    sys.exit(1)

# Try to import genai
try:
    from google import genai

    print("✅ google.genai module imported successfully")
except Exception as e:
    print(f"❌ Failed to import google.genai: {e}")
    sys.exit(1)

# Try to initialize client
try:
    client = genai.Client(api_key=api_key)
    print("✅ Gemini client initialized successfully")
except Exception as e:
    print(f"❌ Failed to initialize Gemini client: {e}")
    import traceback

    print(traceback.format_exc())
    sys.exit(1)

# Try a simple test generation
try:
    print("\nTesting API call...")
    response = client.models.generate_content(
        model="gemini-2.0-flash", contents="Say 'API is working' if you can read this"
    )
    print("✅ API test successful!")
    print(f"   Response: {response.text[:50]}...")
except Exception as e:
    print(f"❌ API call failed: {e}")
    import traceback

    print(traceback.format_exc())
    sys.exit(1)

print("\n" + "=" * 60)
print("✅ All checks passed! Gemini API is working correctly.")
print("=" * 60)
