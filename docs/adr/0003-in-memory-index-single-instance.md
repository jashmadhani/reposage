# In memory index, Cloud Run pinned to one instance

The FAISS index and file contents live in process memory, one Repository at a time, and the Cloud Run service is deployed with `--max-instances 1`. A second instance would not see the index the first one built, and a shared store (Firestore, Cloud Storage, a vector database) is more infrastructure than a demo needs. Restarting the service drops the index; users re-index.

## Consequences

No horizontal scaling and no persistence. Moving to multiple users means a persistent store keyed by repository, recorded as backlog.
