import joblib
import numpy as np
import torch
from transformers import AutoTokenizer, AutoModel

scaler = joblib.load("scaler.pkl")

tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")
bert_model = AutoModel.from_pretrained("bert-base-uncased")

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
bert_model.to(device)
bert_model.eval()

# Cache dictionary
embedding_cache = {}


def get_log_embedding(text):
    # Check cache first
    if text in embedding_cache:
        return embedding_cache[text]

    inputs = tokenizer(
        [text],
        padding=True,
        truncation=True,
        return_tensors="pt",
        max_length=128
    )

    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        outputs = bert_model(**inputs)

    emb = outputs.last_hidden_state[:, 0, :].cpu().numpy()

    # Store in cache
    embedding_cache[text] = emb

    return emb


def build_features(metrics, log_text):
    # Step 1: scale metrics
    metrics_scaled = scaler.transform([metrics])  # (1,14)

    # Step 2: log embedding
    log_emb = get_log_embedding(log_text)  # (1,768)

    # Step 3: interaction
    anchor = metrics_scaled[:, 0:1]  # cpu_user
    interaction = log_emb * anchor   # (1,768)

    # Step 4: combine ALL
    features = np.hstack([
        metrics_scaled,
        log_emb,
        interaction
    ])

    return features