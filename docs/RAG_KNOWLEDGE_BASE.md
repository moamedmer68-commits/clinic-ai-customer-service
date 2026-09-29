# Knowledge retrieval and source-of-truth boundaries

## Current implementation

The FAQ agent uses deterministic lexical retrieval over `data/clinic_faq.json`. `knowledge_base.py` validates the JSON shape, filters malformed entries, ranks question/keyword term coverage, and returns no match below a conservative evidence threshold. The FAQ agent then uses its existing verified-information fallback. FAQ answers must come from clinic-approved content; do not add guessed policies.

## Appointment data is not semantic RAG

`data/doctor_availability.csv` is structured, mutable operational state. Availability, booking, cancellation, and rescheduling continue through the typed tools in `toolkit/toolkits.py`, which validate the schedule and apply guarded CSV mutations. Do not embed appointment rows or use similarity search to determine whether a slot is available. The legacy notebook's pandas filters are historical/reference examples; runtime calls should use the existing tool implementations so all agents share validation and mutation behavior.

## Evaluation and extension

Run `.\\.venv\\Scripts\\python.exe -m pytest tests\\test_knowledge_base.py tests\\test_faq.py -q -p no:cacheprovider` for retrieval/fallback checks, then the full suite. Tests use synthetic FAQ content and do not alter clinic data. Before adopting embeddings/vector storage, supply a reviewed FAQ corpus and create a repeatable evaluation set covering supported paraphrases, unrelated questions, missing evidence, and content updates. Require a safe no-answer result when retrieval confidence is insufficient.

## Limitations

This is lightweight lexical retrieval, not an embedding-based vector database. It has no automatic ingestion pipeline, content approval workflow, or retrieval-quality benchmark over real clinic FAQs. The clinic FAQ file is currently empty, so real clinic-specific answers remain unavailable until authorized content is provided.
