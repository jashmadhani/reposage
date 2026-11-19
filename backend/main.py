"""FastAPI app: /index, /ask, /issue, /health, and the static frontend."""

import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import citations
import fake_mode
import issues
import keys
import limits
import rag_pipeline
import repo_loader
import vector_store
from agent import pipeline

load_dotenv()
keys.activate()

FAKE = os.getenv("REPOSAGE_FAKE") == "1"
if FAKE:
    fake_mode.enable()

log = logging.getLogger("reposage")

app = FastAPI(title="RepoSage")

# Which Repository is indexed: {"url": ..., "owner": ..., "name": ...}
_repo: dict = {}


class IndexRequest(BaseModel):
    repo_url: str


class AskRequest(BaseModel):
    question: str
    mode: str = "agent"


class IssueRequest(BaseModel):
    issue_url: str


def error(code: int, message: str) -> JSONResponse:
    return JSONResponse({"status": "error", "message": message}, status_code=code)


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def over_limit(request: Request, bucket: str) -> bool:
    return not limits.check(client_ip(request), bucket, limits.LIMITS[bucket])


@app.get("/health")
def health():
    return {"ok": True, "repo": _repo.get("name")}


@app.post("/index")
def index_repo(body: IndexRequest, request: Request):
    if over_limit(request, "index"):
        return error(429, "Index limit reached (10 per hour). Try again later.")
    try:
        owner, name = repo_loader.validate_repo_url(body.repo_url)
    except repo_loader.RepoError as e:
        return error(400, str(e))

    started = time.time()
    try:
        repo_path, _ = repo_loader.clone_repo(body.repo_url)
    except Exception as e:
        return error(502, f"Could not clone repository: {e}")
    try:
        files = repo_loader.collect_files(repo_path)
    except repo_loader.RepoError as e:
        return error(400, str(e))
    if not files:
        return error(400, "No indexable source files found.")

    try:
        idx = vector_store.build(name, files)
    except ValueError as e:
        return error(400, str(e))
    except Exception as e:
        return error(502, f"Embedding failed: {e}")
    _repo.clear()
    _repo.update(url=body.repo_url.rstrip("/"), owner=owner, name=name)
    return {
        "status": "ok",
        "repo_name": name,
        "files_indexed": len(files),
        "chunks_indexed": len(idx.chunks),
        "seconds": round(time.time() - started, 2),
    }


async def _with_key_rotation(work):
    """Run `work`; on a quota error switch to the next API key and run it again."""
    while True:
        try:
            return await work()
        except Exception as e:
            if keys.is_quota_error(e) and keys.rotate_after_quota_error():
                log.warning("quota error, switched API key: %s", " ".join(str(e).split())[:160])
                rag_pipeline._client = None  # rebuild the client with the new key
                continue
            return error(502, f"Upstream model error: {e}")


def _finish(answer: str, trace: dict, idx) -> dict:
    return {
        "answer": answer,
        "citations": citations.resolve(answer, idx, _repo["url"]),
        "trace": trace,
    }


@app.post("/ask")
async def ask(body: AskRequest, request: Request):
    idx = vector_store.current()
    if idx is None:
        return error(409, "No repository indexed yet. Index one first.")
    if over_limit(request, "ask"):
        return error(429, "Question limit reached (60 per hour). Try again later.")
    question = body.question.strip()
    if not question or body.mode not in ("agent", "simple"):
        return error(400, "Enter a question and use mode agent or simple.")
    async def work():
        if body.mode == "simple":
            answer, _, trace = rag_pipeline.answer_question(question)
            return _finish(answer, trace, idx)
        llm = fake_mode.llm_for(idx) if FAKE else None
        out = await pipeline.run(question, llm=llm)
        return _finish(out["answer"], out["trace"], idx)

    return await _with_key_rotation(work)


@app.post("/issue")
async def issue(body: IssueRequest, request: Request):
    idx = vector_store.current()
    if idx is None:
        return error(409, "No repository indexed yet. Index one first.")
    if over_limit(request, "ask"):
        return error(429, "Question limit reached (60 per hour). Try again later.")
    try:
        owner, name, _ = issues.parse_issue_url(body.issue_url)
    except issues.IssueError as e:
        return error(400, str(e))
    if (owner.lower(), name.lower()) != (_repo["owner"].lower(), _repo["name"].lower()):
        return error(
            409,
            f"That issue belongs to {owner}/{name}, but {_repo['owner']}/{_repo['name']} is indexed.",
        )
    try:
        found = issues.fetch_issue(body.issue_url)
    except issues.IssueError as e:
        return error(502 if e.upstream else 400, str(e))
    async def work():
        llm = fake_mode.llm_for(idx) if FAKE else None
        out = await pipeline.run("", issue=found, llm=llm)
        return _finish(out["answer"], out["trace"], idx)

    return await _with_key_rotation(work)


_FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
if _FRONTEND.is_dir():
    app.mount("/", StaticFiles(directory=_FRONTEND, html=True), name="frontend")
