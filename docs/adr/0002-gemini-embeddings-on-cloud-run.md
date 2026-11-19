# Gemini embeddings by default instead of local sentence-transformers

v1 embedded locally with all-MiniLM-L6-v2, which pulls PyTorch into the image (over 2 GB) and caps input at 256 word pieces. On Cloud Run that means slow cold starts and silent truncation, so v2 defaults to the Gemini embedding API (768 dimensions, task typed for documents vs queries). The local model stays available behind `EMBEDDING_PROVIDER=local` with `requirements-local.txt` for offline use.

## Consequences

Indexing now needs a Gemini API key and counts against the free tier quota; tests must use a fake embedder.
