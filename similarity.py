import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

def find_similar(query_vector, vectors, top_k=5):
    similarities = cosine_similarity(
        [query_vector],
        vectors
    )[0]

    ranked = sorted(
        enumerate(similarities),
        key=lambda x: x[1],
        reverse=True
    )

    return ranked[:top_k]
