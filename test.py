import joblib
from feature_builder import build_features
import numpy as np

model = joblib.load("anomaly_model.pkl")

metrics = np.random.rand(14)
log_text = "CPU usage is high and system is slow"

features = build_features(metrics, log_text)

pred = model.predict(features)
proba = model.predict_proba(features)

print(pred, proba)