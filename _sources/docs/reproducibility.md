# Reproducibility

## Local environment

Use the project Python environment and dependencies from:

- `requirements.txt`
- `requirements-lock.txt`

Quick environment check script:

- `scripts/00_check_environment.py`

## Build this documentation locally

Install docs builder dependencies:

```bash
pip install -r docs/requirements.txt
```

Build HTML docs:

```bash
jupyter-book build . --config docs/_config.yml --toc docs/_toc.yml
```

Open the generated site:

- `_build/html/index.html`

## Publish on GitHub Pages

The repository includes a workflow that:

1. Installs docs dependencies
2. Builds Jupyter Book into `_build/html`
3. Publishes that folder to `gh-pages`

Push to `main` to trigger deployment.

## Notebook behavior in docs

Notebook execution is disabled during docs build (`execute_notebooks: off`) to keep
builds deterministic and avoid heavy runtime dependencies in CI.
