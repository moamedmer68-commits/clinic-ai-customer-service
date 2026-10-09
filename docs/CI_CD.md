# CI/CD workflow

## Continuous integration (CI)

GitHub Actions runs on every branch push, pull requests targeting `main`, and manual dispatch. The current workflow:

1. Uses Ubuntu with Python 3.12.
2. Installs the curated dependency files `requirements-runtime.txt` and `requirements-test.txt`.
3. Runs `pip check`.
4. Compiles the API, Streamlit UI, agent, tools, knowledge base, and support modules.
5. Runs the full pytest suite with isolated SQLite paths for CI.
6. Builds a container image from the repository Dockerfile.

CI does not publish or deploy the image. A passing run is a code/runtime quality gate, not evidence of a clinic-approved dataset, production security sign-off, or a successful hosted deployment.

## Container scaffold

- `Dockerfile` builds a non-root Python image from the supported runtime manifest.
- `docker-compose.yml` defines local API and Streamlit UI services.
- `.dockerignore` excludes secrets, local runtime data, tests, notebooks, and scratch files.
- Compose binds published ports to localhost by default and requires `OPENAI_API_KEY` and `API_ACCESS_TOKEN`.
- Deployment schedule, FAQ content, conversation checkpoint and handoff queue are mounted/provisioned separately. Never copy the repository's historical schedule CSV into a deployment runtime directory.

Run `docker compose config --quiet` to validate Compose configuration. A container build requires Docker Desktop/the Docker daemon to be running.

## Continuous delivery/deployment (CD)

Automated deployment is intentionally not enabled. No hosting target, production network boundary, managed secret store, approved appointment data source, staffed handoff integration, or protected release environment has been configured yet.

Before adding a deploy job, decide:

1. Hosting target, network exposure, TLS/reverse proxy, and per-user authentication/authorization.
2. Approved current schedule source and how it is provisioned and persisted safely.
3. Secret management, authorization to access patient data, data retention/deletion, encryption, audit controls, and incident ownership.
4. Production database/checkpointer/queue strategy for transactional booking concurrency and multi-host operation.
5. Human escalation notification, staffed ownership, service hours/SLA, and case lifecycle.
6. Backup/restore and rollback plan with a documented post-deploy smoke check.

Once configured, deploy only from a protected branch/environment after CI success, publish an immutable image/artifact, and run authenticated readiness/smoke checks. Do not store credentials or patient data in repository files.

## Current known limitation

Local validation found Docker and Docker Compose CLIs installed, and `docker compose config --quiet` succeeded with placeholder environment values. The Docker Engine pipe was not available at the time of testing, so the image build could not be executed locally. The CI workflow contains the image-build step to perform that verification on a hosted runner.
