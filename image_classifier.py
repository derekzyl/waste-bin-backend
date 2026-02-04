"""
Advanced Image Recognition System for Material Classification
Uses computer vision and machine learning for accurate waste material detection
"""

import os
from typing import Dict, Optional

import cv2
import google.generativeai as genai
import joblib
import numpy as np
from dotenv import load_dotenv
from PIL import Image
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler

# Load environment variables
load_dotenv()


class MaterialClassifier:
    """
    Advanced material classifier using computer vision and ML techniques.
    Combines multiple features: color, texture, shape, and edge detection.
    """

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path
        self.model = None
        self.scaler = StandardScaler()
        self.is_trained = False

        # Load model if path provided
        if model_path and os.path.exists(model_path):
            self.load_model(model_path)
        else:
            # Initialize with default heuristic classifier
            self._initialize_default_classifier()

        # Initialize Gemini
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.gemini_model = genai.GenerativeModel("gemini-flash-latest")
        else:
            print("Warning: GEMINI_API_KEY not found. Gemini classification disabled.")
            self.gemini_model = None

    def _initialize_default_classifier(self):
        """Initialize with a rule-based classifier as fallback"""
        self.is_trained = False
        print("Using rule-based classifier. Train model for better accuracy.")

    def extract_features(self, image: np.ndarray) -> np.ndarray:
        """
        Extract comprehensive features from image for classification.
        Returns a feature vector combining multiple image characteristics.
        """
        features = []

        # Resize image for consistent processing
        img = cv2.resize(image, (224, 224))

        # 1. Color Features (HSV)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        features.extend([
            np.mean(hsv[:, :, 0]),  # Average hue
            np.std(hsv[:, :, 0]),  # Hue variation
            np.mean(hsv[:, :, 1]),  # Average saturation
            np.std(hsv[:, :, 1]),  # Saturation variation
            np.mean(hsv[:, :, 2]),  # Average value/brightness
            np.std(hsv[:, :, 2]),  # Brightness variation
        ])

        # 2. Color Histogram Features
        hist_h = cv2.calcHist([hsv], [0], None, [50], [0, 180])
        hist_s = cv2.calcHist([hsv], [1], None, [50], [0, 256])
        hist_v = cv2.calcHist([hsv], [2], None, [50], [0, 256])
        features.extend([
            np.argmax(hist_h),  # Dominant hue
            np.argmax(hist_s),  # Dominant saturation
            np.argmax(hist_v),  # Dominant brightness
        ])

        # 3. Texture Features (LBP-like)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Calculate local binary patterns
        lbp = self._calculate_lbp(gray)
        hist_lbp = cv2.calcHist([lbp], [0], None, [256], [0, 256])
        features.extend([
            np.mean(hist_lbp),  # Average LBP
            np.std(hist_lbp),  # LBP variation
            np.argmax(hist_lbp),  # Dominant LBP pattern
        ])

        # 4. Edge Features
        edges = cv2.Canny(gray, 50, 150)
        features.extend([
            np.sum(edges > 0) / (edges.shape[0] * edges.shape[1]),  # Edge density
            np.mean(edges[edges > 0])
            if np.any(edges > 0)
            else 0,  # Average edge strength
        ])

        # 5. Shape/Contour Features
        contours, _ = cv2.findContours(
            edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if contours:
            largest_contour = max(contours, key=cv2.contourArea)
            area = cv2.contourArea(largest_contour)
            perimeter = cv2.arcLength(largest_contour, True)
            features.extend([
                area / (img.shape[0] * img.shape[1]),  # Relative area
                (4 * np.pi * area) / (perimeter**2)
                if perimeter > 0
                else 0,  # Circularity
            ])
        else:
            features.extend([0, 0])

        # 6. Color Distribution (Organic vs Non-organic indicators)
        # Organic: more green/brown/yellow
        # Non-organic: more blue/white/metallic

        # Green channel strength (organic indicator)
        green_mask = (hsv[:, :, 0] >= 30) & (hsv[:, :, 0] <= 90) & (hsv[:, :, 1] > 50)
        features.append(np.sum(green_mask) / (img.shape[0] * img.shape[1]))

        # Brown/dark tones (organic indicator)
        brown_mask = (hsv[:, :, 2] < 100) & (hsv[:, :, 1] > 30)
        features.append(np.sum(brown_mask) / (img.shape[0] * img.shape[1]))

        # Blue/metallic tones (non-organic indicator)
        blue_mask = (hsv[:, :, 0] >= 90) & (hsv[:, :, 0] <= 130)
        features.append(np.sum(blue_mask) / (img.shape[0] * img.shape[1]))

        # White/light tones (non-organic indicator)
        white_mask = (hsv[:, :, 2] > 200) & (hsv[:, :, 1] < 30)
        features.append(np.sum(white_mask) / (img.shape[0] * img.shape[1]))

        # 7. Color Diversity (entropy)
        hist_r = cv2.calcHist([img], [0], None, [256], [0, 256])
        hist_g = cv2.calcHist([img], [1], None, [256], [0, 256])
        hist_b = cv2.calcHist([img], [2], None, [256], [0, 256])

        def entropy(hist):
            hist = hist / (np.sum(hist) + 1e-10)
            hist = hist[hist > 0]
            return -np.sum(hist * np.log2(hist + 1e-10))

        features.extend([
            entropy(hist_r),
            entropy(hist_g),
            entropy(hist_b),
        ])

        return np.array(features, dtype=np.float32)

    def _calculate_lbp(
        self, image: np.ndarray, radius: int = 1, n_points: int = 8
    ) -> np.ndarray:
        """
        Calculate Local Binary Pattern for texture analysis.
        Simplified version for performance.
        """
        h, w = image.shape
        lbp = np.zeros_like(image)

        for i in range(radius, h - radius):
            for j in range(radius, w - radius):
                center = image[i, j]
                code = 0

                # Sample points in a circle
                for k in range(n_points):
                    angle = 2 * np.pi * k / n_points
                    x = int(i + radius * np.cos(angle))
                    y = int(j + radius * np.sin(angle))

                    if 0 <= x < h and 0 <= y < w:
                        if image[x, y] >= center:
                            code |= 1 << k

                lbp[i, j] = code

        return lbp

    def classify(self, image: np.ndarray) -> Dict[str, any]:
        """
        Classify material type from image.
        Returns: {"material": "ORGANIC" or "NON_ORGANIC", "confidence": float, ...}
        """
        if image is None or image.size == 0:
            return {"material": "UNKNOWN", "confidence": 0.0, "error": "Invalid image"}

        # Extract features
        features = self.extract_features(image)
        features = features.reshape(1, -1)

        # Try Gemini Classification first
        if self.gemini_model:
            try:
                # Convert CV2 BGR to PIL RGB
                img_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(img_rgb)

                response = self.gemini_model.generate_content([
                    "Classify this waste material image into exactly one of these two categories: 'ORGANIC' or 'NON_ORGANIC'. "
                    'Return ONLY a JSON object with this format: {"material": "CATEGORY", "confidence": 0.95}',
                    pil_image,
                ])

                # Parse response
                import json

                text_response = response.text.strip()
                # Handle potential markdown code blocks in response
                if text_response.startswith("```json"):
                    text_response = text_response[7:-3]
                elif text_response.startswith("```"):
                    text_response = text_response[3:-3]

                result = json.loads(text_response)

                return {
                    "material": result.get("material", "UNKNOWN"),
                    "confidence": float(result.get("confidence", 0.0)),
                    "method": "gemini_api",
                    "raw_response": text_response,
                }

            except Exception as e:
                print(f"Gemini API error: {e}, falling back to local model")
                # Fallback to local execution below

        if self.is_trained and self.model is not None:
            # Use trained ML model
            try:
                features_scaled = self.scaler.transform(features)
                prediction = self.model.predict(features_scaled)[0]
                probabilities = self.model.predict_proba(features_scaled)[0]

                material = "ORGANIC" if prediction == 1 else "NON_ORGANIC"
                confidence = float(max(probabilities))

                return {
                    "material": material,
                    "confidence": confidence,
                    "method": "ml_model",
                    "probabilities": {
                        "organic": float(
                            probabilities[1] if len(probabilities) > 1 else 0.5
                        ),
                        "non_organic": float(
                            probabilities[0] if len(probabilities) > 0 else 0.5
                        ),
                    },
                }
            except Exception as e:
                print(f"ML model error: {e}, falling back to rule-based")

        # Fallback to rule-based classification
        return self._rule_based_classify(image, features[0])

    def _rule_based_classify(
        self, image: np.ndarray, features: np.ndarray
    ) -> Dict[str, any]:
        """
        Rule-based classification using feature analysis.
        """
        # Feature indices from extract_features
        avg_hue = features[0]
        avg_sat = features[2]
        green_ratio = features[18]
        brown_ratio = features[19]
        blue_ratio = features[20]
        white_ratio = features[21]

        # Organic indicators
        organic_score = 0
        if 30 <= avg_hue <= 90:  # Green/brown hues
            organic_score += 2
        if avg_sat > 80:  # High saturation (natural colors)
            organic_score += 1
        if green_ratio > 0.2:  # Significant green presence
            organic_score += 2
        if brown_ratio > 0.15:  # Brown/dark tones
            organic_score += 1

        # Non-organic indicators
        non_organic_score = 0
        if (avg_hue < 30 or avg_hue > 150) and avg_sat < 50:  # Blue/white tones
            non_organic_score += 2
        if blue_ratio > 0.2:  # Blue/metallic presence
            non_organic_score += 2
        if white_ratio > 0.3:  # White/light tones
            non_organic_score += 2
        if avg_sat < 30:  # Low saturation (synthetic colors)
            non_organic_score += 1

        # Determine classification
        if organic_score > non_organic_score:
            material = "ORGANIC"
            confidence = min(0.85, 0.60 + (organic_score - non_organic_score) * 0.05)
        elif non_organic_score > organic_score:
            material = "NON_ORGANIC"
            confidence = min(0.85, 0.60 + (non_organic_score - organic_score) * 0.05)
        else:
            material = "ORGANIC"  # Default to organic
            confidence = 0.60

        return {
            "material": material,
            "confidence": float(confidence),
            "method": "rule_based",
            "scores": {"organic": organic_score, "non_organic": non_organic_score},
        }

    def train_model(
        self,
        training_data: list,
        labels: list,
        save_path: str = "models/material_classifier.pkl",
    ):
        """
        Train a Random Forest classifier on labeled data.

        Args:
            training_data: List of images (numpy arrays)
            labels: List of labels (0 for NON_ORGANIC, 1 for ORGANIC)
            save_path: Path to save trained model
        """
        print("Extracting features from training data...")
        features_list = []
        for img in training_data:
            features = self.extract_features(img)
            features_list.append(features)

        X = np.array(features_list)
        y = np.array(labels)

        # Scale features
        X_scaled = self.scaler.fit_transform(X)

        # Train Random Forest classifier
        print("Training model...")
        self.model = RandomForestClassifier(
            n_estimators=100, max_depth=20, random_state=42, n_jobs=-1
        )
        self.model.fit(X_scaled, y)

        self.is_trained = True

        # Save model
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        model_data = {"model": self.model, "scaler": self.scaler, "is_trained": True}
        joblib.dump(model_data, save_path)
        print(f"Model trained and saved to {save_path}")

        # Calculate accuracy
        accuracy = self.model.score(X_scaled, y)
        print(f"Training accuracy: {accuracy:.2%}")

    def load_model(self, model_path: str):
        """Load a trained model from file"""
        try:
            model_data = joblib.load(model_path)
            self.model = model_data["model"]
            self.scaler = model_data["scaler"]
            self.is_trained = model_data.get("is_trained", True)
            print(f"Model loaded from {model_path}")
        except Exception as e:
            print(f"Error loading model: {e}")
            self._initialize_default_classifier()
