import os
import sys

print("Sys Path:")
for p in sys.path:
    print(p)

print("\nSite Packages Content:")
try:
    import site

    packages_dir = site.getsitepackages()[0]
    print(f"Checking {packages_dir}")
    if os.path.exists(packages_dir):
        for item in os.listdir(packages_dir):
            if "numpy" in item:
                print(item)
except Exception as e:
    print(f"Error checking site packages: {e}")

print("\nEnvironment Variables:")
for key, value in os.environ.items():
    if "PYTHON" in key:
        print(f"{key}={value}")
