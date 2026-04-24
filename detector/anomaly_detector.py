# Anomaly detection logic
import joblib
from feature_builder import build_features

model = joblib.load("anomaly_model.pkl")

def predict_anomaly(metrics, log_text):
    features = build_features(metrics, log_text)

    prediction = model.predict(features)[0]
    proba = model.predict_proba(features)[0]

    return prediction, proba