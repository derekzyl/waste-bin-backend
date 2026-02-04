"""
Training script for material classification model.
Collect training images and label them, then run this script to train the model.
"""

import cv2
import numpy as np
import os
from image_classifier import MaterialClassifier
from pathlib import Path

def load_training_data(data_dir: str):
    """
    Load training images from directory structure:
    data_dir/
        organic/
            image1.jpg
            image2.jpg
            ...
        non_organic/
            image1.jpg
            image2.jpg
            ...
    """
    images = []
    labels = []
    
    organic_dir = os.path.join(data_dir, "organic")
    non_organic_dir = os.path.join(data_dir, "non_organic")
    
    # Load organic images (label = 1)
    if os.path.exists(organic_dir):
        for img_file in os.listdir(organic_dir):
            if img_file.lower().endswith(('.jpg', '.jpeg', '.png')):
                img_path = os.path.join(organic_dir, img_file)
                img = cv2.imread(img_path)
                if img is not None:
                    images.append(img)
                    labels.append(1)  # ORGANIC
                    print(f"Loaded organic: {img_file}")
    
    # Load non-organic images (label = 0)
    if os.path.exists(non_organic_dir):
        for img_file in os.listdir(non_organic_dir):
            if img_file.lower().endswith(('.jpg', '.jpeg', '.png')):
                img_path = os.path.join(non_organic_dir, img_file)
                img = cv2.imread(img_path)
                if img is not None:
                    images.append(img)
                    labels.append(0)  # NON_ORGANIC
                    print(f"Loaded non-organic: {img_file}")
    
    return images, labels

def main():
    # Configuration
    data_dir = "training_data"  # Directory with organic/ and non_organic/ subdirectories
    model_path = "models/material_classifier.pkl"
    
    print("=" * 60)
    print("Material Classification Model Training")
    print("=" * 60)
    
    # Load training data
    print(f"\nLoading training data from {data_dir}...")
    images, labels = load_training_data(data_dir)
    
    if len(images) == 0:
        print("ERROR: No training images found!")
        print(f"Please create directory structure:")
        print(f"  {data_dir}/")
        print(f"    organic/")
        print(f"      image1.jpg")
        print(f"      image2.jpg")
        print(f"      ...")
        print(f"    non_organic/")
        print(f"      image1.jpg")
        print(f"      image2.jpg")
        print(f"      ...")
        return
    
    print(f"\nLoaded {len(images)} training images")
    print(f"  Organic: {labels.count(1)}")
    print(f"  Non-organic: {labels.count(0)}")
    
    # Initialize classifier
    classifier = MaterialClassifier()
    
    # Train model
    print("\nTraining model...")
    classifier.train_model(images, labels, save_path=model_path)
    
    print("\n" + "=" * 60)
    print("Training completed!")
    print(f"Model saved to: {model_path}")
    print("=" * 60)
    print("\nTo use the trained model, set environment variable:")
    print(f"  export MODEL_PATH={model_path}")
    print("\nOr update main.py to use the model path.")

if __name__ == "__main__":
    main()

