# Contributing

Thank you for your interest in contributing to this project. To keep the process smooth and the codebase maintainable, please follow these brief guidelines.

## Development Workflow

1. **Fork** the repository to your own GitHub account.
2. **Clone** your fork locally.
3. **Create a branch** for your feature or bugfix (`git checkout -b feature/your-feature-name`).
4. **Commit** your changes with clear, descriptive commit messages.
5. **Push** the branch to your fork (`git push origin feature/your-feature-name`).
6. **Open a Pull Request** against the `main` branch of the original repository.

## Setting Up Your Environment

This project uses [uv](https://github.com/astral-sh/uv) for dependency management. To set up your local environment with all required development tools, run:

```bash
uv sync --group dev

```

## Coding Standards

To maintain a clean and reliable codebase, we enforce strict linting, formatting, and type-checking. Please ensure your code passes the following checks before opening a Pull Request.

### 1. Linting and Formatting (Ruff)

We use [ruff](https://github.com/astral-sh/ruff) to handle both linting and code formatting.

To format your code automatically:

```bash
uv run ruff format src/ tests/

```

To check for linting errors and stylistic issues:

```bash
uv run ruff check src/ tests/

```

### 2. Type Checking (Ty)

All new functions, classes, and methods must include standard Python type hints. We use [ty](https://github.com/astral-sh/ty) for static type checking to catch errors before runtime.

To run the type checker:

```bash
uv run ty check src/ tests/

```

### 3. Testing (Pytest)

If you are adding a new feature or fixing a bug, please write or update the corresponding tests.

To run the test suite:

```bash
uv run pytest -v

```

## Pull Request Checklist

Before submitting your Pull Request, please verify that:

* Your code is fully formatted with `ruff`.
* There are no outstanding `ty` type errors.
* All `pytest` tests pass successfully locally.
* You have updated the `README.md` if your changes introduce new user-facing features.
