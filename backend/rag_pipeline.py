"""Local embedding + FAISS retrieval, and the single call out to Gemini."""

import os

import faiss
import google.generativeai as genai
import numpy as np
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

load_dotenv()

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
GENERATION_MODEL_NAME = "gemini-1.5-flash"
TOP_K = 5

# The whole index lives in this module's globals. Nothing is written to disk,
# so restarting the server means re-indexing.
_embedding_model = None
_index = None
_documents = []  # parallel to the index: _documents[i] is (path, text) for vector i


def get_embedding_model():
    """Load the sentence-transformers model once and reuse it."""
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _embedding_model


def build_index(files):
    """Embed one vector per file and put them all in a fresh FAISS index."""
    global _index, _documents

    model = get_embedding_model()
    texts = [text for _path, text in files]
    embeddings = model.encode(texts, show_progress_bar=False)
    embeddings = np.array(embeddings).astype("float32")

    # IndexFlatL2 is a brute-force exact search over L2 distance. Fine at this scale.
    _index = faiss.IndexFlatL2(embeddings.shape[1])
    _index.add(embeddings)
    _documents = files

    return len(files)


def is_indexed():
    return _index is not None


def retrieve(question):
    """Embed the question and return the TOP_K nearest (path, text) pairs."""
    model = get_embedding_model()
    question_embedding = model.encode([question])
    question_embedding = np.array(question_embedding).astype("float32")

    k = min(TOP_K, len(_documents))
    _distances, indices = _index.search(question_embedding, k)

    return [_documents[i] for i in indices[0]]


def build_prompt(question, retrieved):
    """Assemble the retrieved file contents into one grounded prompt."""
    context_blocks = []
    for path, text in retrieved:
        context_blocks.append(f"--- FILE: {path} ---\n{text}")
    context = "\n\n".join(context_blocks)

    return (
        "You are answering questions about a code repository.\n"
        "Answer ONLY using the file contents provided below. "
        "If the answer is not in these files, say you cannot find the answer "
        "in the retrieved files. Do not guess and do not use outside knowledge.\n\n"
        f"FILE CONTENTS:\n{context}\n\n"
        f"QUESTION: {question}\n\n"
        "ANSWER:"
    )


def generate_answer(prompt):
    """The only place this project talks to a generation API. Swap here."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "GEMINI_API_KEY is not set. Add it to your .env file."

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(GENERATION_MODEL_NAME)
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"The generation API returned an error: {e}"


def answer_question(question):
    """Retrieve, prompt, generate. Returns (answer, source_paths)."""
    retrieved = retrieve(question)
    prompt = build_prompt(question, retrieved)
    answer = generate_answer(prompt)
    sources = [path for path, _text in retrieved]
    return answer, sources
