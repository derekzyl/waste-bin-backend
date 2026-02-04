# Smart Waste Bin Backend API

FastAPI backend for material detection and bin management with advanced image recognition.

## Features

- **Advanced Image Recognition**: Computer vision and ML-based material classification
- **Multiple Classification Methods**: ML model or rule-based fallback
- **Feature Extraction**: Comprehensive feature analysis (color, texture, shape, edges)
- **Model Training**: Script to train custom models on your data
- **RESTful API**: Easy-to-use endpoints for all operations

## Installation

```bash
pip install -r requirements.txt
```

## Running

```bash
python main.py
```

Or with uvicorn for development:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`
- Alternative Docs: `http://localhost:8000/redoc`

## Image Recognition System

### How It Works

The system uses a multi-feature approach for material classification:

1. **Color Analysis**: HSV color space, color histograms, dominant colors
2. **Texture Analysis**: Local Binary Patterns (LBP) for texture features
3. **Edge Detection**: Canny edge detection for shape analysis
4. **Contour Analysis**: Shape and circularity measurements
5. **Color Distribution**: Organic vs non-organic color indicators
6. **Color Diversity**: Entropy-based color variation analysis

### Classification Methods

#### 1. Machine Learning Model (Recommended)
- Uses Random Forest classifier
- Trained on labeled data
- Higher accuracy
- Requires training data

#### 2. Rule-Based Classifier (Default)
- Works out of the box
- No training required
- Good baseline accuracy
- Based on color and texture heuristics

### Training a Custom Model

1. **Prepare Training Data**:
   ```
   training_data/
     organic/
       image1.jpg
       image2.jpg
       ...
     non_organic/
       image1.jpg
       image2.jpg
       ...
   ```

2. **Run Training Script**:
   ```bash
   python train_model.py
   ```

3. **Use Trained Model**:
   - Set environment variable: `export MODEL_PATH=models/material_classifier.pkl`
   - Or update `main.py` to use the model path

## API Endpoints

### Material Detection

**POST** `/api/detect`
- Accepts: JPEG image file
- Returns: Classification result with material type and confidence

Example:
```bash
curl -X POST "http://localhost:8000/api/detect" \
  -F "file=@waste_image.jpg"
```

Response:
```json
{
  "material": "ORGANIC",
  "confidence": 0.85,
  "method": "ml_model",
  "probabilities": {
    "organic": 0.85,
    "non_organic": 0.15
  }
}
```

### Bin Management

- `GET /api/bins` - Get all bins status
- `GET /api/bins/{bin_id}` - Get specific bin status
- `POST /api/bins/update` - Update bin status from ESP32
- `POST /api/bins/{bin_id}/reset` - Reset bin (maintenance)
- `GET /api/stats` - Get overall statistics

## Configuration

### Environment Variables

- `MODEL_PATH`: Path to trained model file (default: `models/material_classifier.pkl`)
- `PORT`: Server port (default: 8000)
- `HOST`: Server host (default: 0.0.0.0)

### Model Performance

- **Rule-based**: ~70-75% accuracy
- **ML Model (trained)**: ~85-95% accuracy (depends on training data quality)

## Improving Accuracy

1. **Collect More Training Data**: More diverse images = better accuracy
2. **Image Quality**: Ensure good lighting and focus in training images
3. **Data Balance**: Equal number of organic and non-organic samples
4. **Augmentation**: Use data augmentation for better generalization
5. **Feature Engineering**: Add domain-specific features if needed

## Production Considerations

1. **Database**: Replace in-memory storage with PostgreSQL/MongoDB
2. **Model Versioning**: Track model versions and performance
3. **Caching**: Cache classification results for similar images
4. **Monitoring**: Add logging and performance monitoring
5. **Security**: Add authentication and rate limiting
6. **GPU Support**: Use GPU-accelerated TensorFlow for faster inference

## Troubleshooting

**Model not loading?**
- Check model file path
- Ensure joblib is installed
- Verify model file format

**Low accuracy?**
- Collect more training data
- Improve image quality
- Check for class imbalance
- Try different features or models

**Slow inference?**
- Use GPU acceleration
- Reduce image size
- Optimize feature extraction
- Use model quantization
