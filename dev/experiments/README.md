# Development Experiments

This folder contains local exploratory scripts used while debugging LangGraph checkpointing and API/session behavior.

- These files are not part of the production application or the automated pytest suite.
- Keep them separate from `tests/`, which contains maintained automated regression tests.
- Review and promote a useful experiment into `tests/` only after converting it into deterministic assertions and fixtures.
- Do not add secrets, `.env` files, real patient data, or live appointment records here.
- Preserve these scripts unless their owner explicitly approves deletion.
