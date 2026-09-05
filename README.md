# RepoSage

A retrieval augmented generation assistant that answers natural language questions
about a public GitHub repository. Embeddings and search run locally; only the
retrieved file contents and your question are sent to the generation API.

## Architecture

1. You submit a public GitHub repository URL.
2. The backend clones it into a local `temp_repo/` directory with GitPython.
3. The backend walks the clone and collects source files by extension, skipping
   excluded paths, secret-shaped filenames, and files over 100 KB.
4. Each file's full text is embedded locally with `sentence-transformers`, model
   `all-MiniLM-L6-v2`. No embedding API is called.
5. The embeddings go into a FAISS `IndexFlatL2` held in memory.
6. You ask a question. It is embedded with the same model, and FAISS returns the
   top 5 nearest files.
7. Those file contents are assembled into one grounded prompt and sent to Gemini
   (`gemini-1.5-flash`) for generation.
8. The answer is returned to the frontend along with the retrieved file paths.

## Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Copy the example env file and add your key:

```bash
cp ../.env.example ../.env
# then edit .env and set GEMINI_API_KEY=your_key
```

Get a key from https://aistudio.google.com/app/apikey

## Run

Start the backend from the `backend/` directory:

```bash
cd backend
source venv/bin/activate
uvicorn main:app --reload --port 8000
```

Then open `frontend/index.html` directly in a browser. CORS is enabled for local
development, so no web server is needed for the frontend.

Paste a repository URL, click **Index Repository**, wait for it to finish (the
first run also downloads the embedding model), then ask a question.

## Configuration points

| What | Where |
| --- | --- |
| Included file extensions | `INCLUDED_EXTENSIONS` in `backend/repo_loader.py` |
| Excluded filename patterns | `EXCLUDED_FILE_PATTERNS` in `backend/repo_loader.py` |
| Excluded directories | `EXCLUDED_DIRECTORIES` in `backend/repo_loader.py` |
| Max file size | `MAX_FILE_SIZE_BYTES` in `backend/repo_loader.py` |
| Number of files retrieved | `TOP_K` in `backend/rag_pipeline.py` |
| Generation provider | `generate_answer()` in `backend/rag_pipeline.py` |

## Known limitations

- **Whole files are embedded, not chunks.** One file produces exactly one vector.
  There is no chunking, no overlap, and no token-aware splitter. This caps
  retrieval precision on large files: a 900 line file with one relevant function
  is represented by a single averaged vector, so the signal from that function is
  diluted by everything else in the file. Files longer than the embedding model's
  input limit (256 word pieces for `all-MiniLM-L6-v2`) are silently truncated, so
  content past that point is invisible to retrieval.
- The index lives in memory only. Restarting the backend means re-indexing.
- Only one repository is indexed at a time; indexing a new one replaces the old.
- No conversation history. Each question is answered independently.
- Retrieval always returns the top 5 files whether or not they are actually
  relevant, so an off-topic question still pulls in context.
