# Knowledge retrieval and source-of-truth boundaries

## Phase 7 implementation

The FAQ agent now uses a persistent semantic retrieval layer backed by embeddings and a file-based vector index.

### Retrieval flow

1. Load `data/clinic_faq.json`.
2. Validate and normalize approved FAQ records.
3. Build embeddings from each question plus approved keywords.
4. Persist normalized records in `metadata.json` and normalized vectors in `embeddings.npy`.
5. Reuse the cached index when the FAQ content fingerprint and embedding model match.
6. Embed the patient query.
7. Rank candidate records by cosine similarity.
8. Optionally restrict results by source IDs and configure `top_k`.
9. Reject weak evidence below the configured similarity threshold.
10. Return the grounded answer and source ID when available.

The default embedding model is `text-embedding-3-small` through `langchain-openai`. Override it with `FAQ_EMBEDDING_MODEL`.

The default persistent index location is `data/faq_index`. Override it with `FAQ_RAG_INDEX_PATH`.

## Ingestion

Build or rebuild the vector index with:

```powershell
.\.venv\Scripts\python.exe -m knowledge_base --source data\clinic_faq.json --index-dir data\faq_index
```

Only clinic-approved FAQ content may be indexed. The ingestion process is content-hash aware and rebuilds the index when the validated FAQ corpus changes.

The application also performs lazy load/build when semantic FAQ retrieval needs an index. This is convenient for the local prototype; production deployment should build the index as a controlled deployment/content-update step rather than during a patient request.

## Grounding and no-answer behavior

The FAQ node never generates clinic facts from retrieved text. It returns the stored approved answer from the matched record.

When no record reaches the evidence threshold, the FAQ node creates a local human-handoff case with status pending and returns a truthful case ID/status message. When the embedding/indexing service is unavailable, the FAQ node also escalates instead of inventing an answer or claiming human contact.

Source IDs are surfaced as:

```text
Source: <id>
```

This is a lightweight trace reference. Full citation rendering is still a future enhancement.

## Evaluation

Synthetic evaluation cases live in:

- `tests/fixtures/synthetic_faq.json`
- `tests/fixtures/faq_retrieval_eval.json`

The evaluator reports:

- `hit_rate_at_k`
- `mrr` (mean reciprocal rank)
- `no_answer_rate`

The current deterministic synthetic suite verifies 100% hit rate at k=1, MRR 1.0, and 100% no-answer rate for the unsupported cases.

This evaluation is not a substitute for evaluation on a clinic-approved corpus. Before production use, add reviewed paraphrases, unrelated questions, content-update cases, and source-filter cases owned by the clinic.

## Appointment data is not semantic RAG

`data/doctor_availability.csv` is structured, mutable operational state. Availability, booking, cancellation, and rescheduling continue through the typed tools in `toolkit/toolkits.py`.

Do not embed appointment rows or use similarity search to determine whether a slot is available. Do not use the FAQ index to mutate appointment data.

The legacy notebook copy is a historical/reference artifact; runtime appointment calls should use the existing structured tool path.

## Current limitation

`data/clinic_faq.json` remains intentionally empty because no clinic-approved FAQ corpus has been supplied yet. The semantic RAG implementation is present and tested with synthetic content, but real clinic-specific answers cannot be served until approved content is loaded and indexed.

The vector index is file-based (`.npy` + JSON metadata), which is appropriate for the current local/single-host prototype. A production multi-instance deployment should migrate the vector store and content update process to infrastructure designed for shared persistence and controlled updates.