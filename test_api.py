import os
import subprocess
import time

import cv2
import numpy as np
import requests

# Configuration
API_URL = "http://127.0.0.1:8000/api/detect"
IMG_SIZE = (224, 224)
GREEN_COLOR = (0, 255, 0)  # Organic-like


def create_sample_image(filename="test_image.jpg"):
    img = np.zeros((*IMG_SIZE, 3), dtype=np.uint8)
    img[:] = GREEN_COLOR
    cv2.imwrite(filename, img)
    print(f"Created sample image: {filename}")
    return filename


def test_endpoint(image_path):
    print(f"Sending {image_path} to {API_URL}...")
    try:
        with open(image_path, "rb") as f:
            files = {"file": f}
            response = requests.post(API_URL, files=files)

        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")

        if response.status_code == 200:
            return True
        else:
            return False
    except Exception as e:
        print(f"Request failed: {e}")
        return False


def main():
    image_path = create_sample_image()

    # Check if server is running, if not start it
    server_process = None
    try:
        requests.get("http://127.0.0.1:8000/")
        print("Server is already running.")
    except requests.exceptions.ConnectionError:
        print("Starting server...")
        env = os.environ.copy()
        # Ensure PYTHONPATH is unset for local run compatibility
        if "PYTHONPATH" in env:
            del env["PYTHONPATH"]

        server_process = subprocess.Popen(
            ["uv", "run", "fastapi", "dev", "main.py"],
            cwd=os.getcwd(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        print("Waiting for server startup (10s)...")
        time.sleep(10)

    try:
        success = test_endpoint(image_path)
        if success:
            print("\nSUCCESS: API Endpoint working correctly.")
        else:
            print("\nFAILURE: API Endpoint returned error.")

    finally:
        # cleanup
        if os.path.exists(image_path):
            os.remove(image_path)

        if server_process:
            print("Stopping test server...")
            server_process.terminate()
            server_process.wait()


if __name__ == "__main__":
    main()
