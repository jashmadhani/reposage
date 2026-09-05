"""FastAPI app exposing /index and /ask."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import rag_pipeline
import repo_loader

app = FastAPI(title="RepoSage")

# Wide open, because the frontend is opened straight from the filesystem.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class IndexRequest(BaseModel):
    repo_url: str


class AskRequest(BaseModel):
    question: str


@app.post("/index")
def index_repo(request: IndexRequest):
    try:
        repo_path, repo_name = repo_loader.clone_repo(request.repo_url)
    except Exception as e:
        return {"status": "error", "message": f"Could not clone repository: {e}"}

    files = repo_loader.collect_files(repo_path)
    if not files:
        return {"status": "error", "message": "No indexable source files found."}

    count = rag_pipeline.build_index(files)
    return {"status": "ok", "files_indexed": count, "repo_name": repo_name}


@app.post("/ask")
def ask(request: AskRequest):
    if not rag_pipeline.is_indexed():
        return {"status": "error", "message": "No repository indexed yet. Index one first."}

    answer, sources = rag_pipeline.answer_question(request.question)
    return {"answer": answer, "sources": sources}
