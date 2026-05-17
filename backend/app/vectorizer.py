from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')

def embed_text(text: str):

    if isinstance(text, str):
        text = [text]

    # Return NumPy arrays so sklearn cosine_similarity works on any device,
    # including Apple Silicon MPS where Torch tensors are not NumPy-convertible directly.
    return model.encode(text, convert_to_numpy=True)



