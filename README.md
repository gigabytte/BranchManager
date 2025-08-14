# BranchManager

![branchmanager-logo](docs/images/branchmanager-logo.png)

Python based CLI tool for managing stale/dead branches in hosted Git solutions (ie. Github Orgs)

## Advantages over existing solutions

- Scoped to the repo the workflow is owned by
- Requires a workflow per repo scoped cannot take a list of repos or use a regex like statement for filtering all repos in a given "org"
- deletes branch without warning, no commit msg or notif

## How does it work?

1. Scans for all repos in a given org (ie. GitHub org) and filters based on regex provided in config file
2. Scans and filters all branches on the filtered repos based on regex provided in config file
3. Gets the latest commit for a given branch from our filtered branch list. Rejects or keeps branch based on commit author via regex provided in config file
4. Creates comment notifying the author of said commit that the branch is stale or deletes the branch based on the configured number of days in the config file

## CLI Options docs

```bash
$ uv run branch-manager --help

  Manages stale branches in your managed Git Hosting platform

Options:
  -v, --verbose      Enable verbose output
  --version          Show the version and exit.
  -c, --config PATH  Path to YAML config file
  -d, --dry-run      Dry run mode
  --help             Show this message and exit.
```

## Declarative YAML config

CLI tool uses a Declarative YAML config file for specifying git repos to perform deprecation actions on stale branches.
API docs @ `docs/api/docs.md`

## Quick Start

### Prerequisites

- Python 3.13+
- [UV](https://docs.astral.sh/uv/) package manager

### Installation

#### 1. Clone the repository

  ```bash
  git clone <your-repo-url>
  cd branch-manager
  ```

#### 2. Install dependencies

  ```bash
  uv sync
  ```

#### 3. Install development dependencies

  ```bash
  uv sync --extra dev
  ```

### Usage

Run the CLI application:

```bash
uv run branch-manager
```

With verbose output:

```bash
uv run branch-manager --verbose
```

## Development

### Running Tests

```bash
uv run pytest
```

With coverage:

```bash
uv run pytest --cov=branch_manager --cov-report=html
```

### Code Quality

Format code:

```bash
uv run black .
```

Lint and fix:

```bash
uv run ruff check --fix .
```

Type checking:

```bash
uv run mypy .
```

### Pre-commit Hooks

Install pre-commit hooks:

```bash
uv run pre-commit install
```
