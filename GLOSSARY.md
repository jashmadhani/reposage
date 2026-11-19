# RepoSage

RepoSage answers questions about a public code repository and turns its issues into fix plans, citing exact lines it has verified.

## Language

### Input

**Repository**:
The public GitHub project being indexed. Exactly one is indexed at a time.
_Avoid_: repo (in UI copy), project, codebase

**Question**:
A natural language query about the indexed Repository.
_Avoid_: prompt, query (in UI copy)

**Issue**:
A GitHub issue from the indexed Repository, given by its URL, that the user wants a Fix Plan for.
_Avoid_: ticket, bug report

### Retrieval

**Chunk**:
A contiguous range of lines from one file, the unit that is embedded and retrieved. A Python Chunk is one top level function or class where possible.
_Avoid_: snippet, passage, document

**Evidence**:
The set of Chunks and exact line reads the Researcher gathered for one Question or Issue.
_Avoid_: context, sources

### Output

**Answer**:
The final response to a Question, made only of claims backed by Citations.

**Fix Plan**:
The final response to an Issue: files and line ranges to change, ordered steps, tests to update, and risks.
_Avoid_: solution, patch

**Citation**:
A reference to a file and line range, written `path:start-end`, attached to one claim.
_Avoid_: source, reference

**Verified Citation**:
A Citation whose line range the Reviewer re-read and confirmed supports its claim. Only Verified Citations appear in an Answer or Fix Plan.

**Trace**:
The record of one request: agent steps, tool calls, tokens, latency and estimated cost.
_Avoid_: logs, telemetry

### Agents

**Researcher**:
The agent that gathers Evidence by calling retrieval tools in a loop.

**Writer**:
The agent that turns Evidence into a draft Answer or Fix Plan.

**Reviewer**:
The agent that re-reads every Citation in a draft and either approves it or sends back the unsupported claims, at most twice.
_Avoid_: critic, judge, verifier
