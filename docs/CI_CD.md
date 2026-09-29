# CI/CD workflow

## Current continuous integration (CI)

GitHub Actions runs on every branch push, pull requests targeting `main`, and manual dispatch.
The workflow uses Ubuntu with Python 3.12, installs project dependencies and pytest, checks dependency consistency, compiles application modules, and runs the test suite.

CI is a quality gate: a green run means the configured checks passed for that commit. It does not publish or deploy the application.

## Continuous delivery/deployment (CD)

Automated deployment is intentionally not enabled yet. The repository currently has no Dockerfile or deployment manifest, and no hosting target/environment has been selected in the project configuration. The application also relies on a CSV schedule and an OpenAI API key; deployment must define safe persistent storage and secret handling before publishing a live instance.

Before adding deployment, decide:

1. Hosting target (for example AWS ECS, a VM, or another platform).
2. Container/runtime and health-check contract.
3. How the schedule data is provisioned and persisted safely (do not deploy the development CSV containing patient records).
4. GitHub Actions secrets/role-based cloud authentication and protected production environment approval.
5. Rollback and post-deployment smoke-test strategy.

Once those decisions are configured, add a deployment job that depends on successful CI, publishes an immutable image/artifact, deploys only from the protected `main` branch, and runs a health check. Do not store credentials in repository files.
