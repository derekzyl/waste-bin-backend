try:
    import numpy

    print(f"NumPy version: {numpy.__version__}")
    print(f"NumPy path: {numpy.__file__}")
except ImportError as e:
    print(f"NumPy Import Error: {e}")

try:
    import cv2

    print(f"OpenCV version: {cv2.__version__}")
except ImportError as e:
    print(f"OpenCV Import Error: {e}")
