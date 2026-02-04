import numpy as np
from dotenv import load_dotenv
from image_classifier import MaterialClassifier
from PIL import Image

load_dotenv()


def create_synthetic_image(color):
    img = Image.new("RGB", (224, 224), color)
    return np.array(img)


def main():
    print("Initializing Classifier...")
    try:
        classifier = MaterialClassifier()
    except Exception as e:
        print(f"Failed to initialize classifier: {e}")
        return

    if classifier.client:
        print("Gemini client initialized.")
    else:
        print("Gemini client NOT initialized. Check API Key.")
        # Proceeding to test fallback/behavior anyway

    print("Creating synthetic organic-like (green) image...")
    img = create_synthetic_image((0, 255, 0))  # Green

    print("Classifying...")
    try:
        result = classifier.classify(img)
        print("\nResult:")
        print(result)

        if result.get("method") == "gemini_api":
            print("\nSUCCESS: Used Gemini API")
        else:
            print("\nFAILURE: Did not use Gemini API (Fallback used)")

    except Exception as e:
        print(f"Classification failed: {e}")


if __name__ == "__main__":
    main()
