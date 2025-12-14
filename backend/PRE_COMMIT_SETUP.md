# Pre-commit Hooks Setup Guide

This guide explains how to set up and use pre-commit hooks to ensure code quality for the backend Python code.

## What is Pre-commit?

Pre-commit is a framework for managing git pre-commit hooks. It automatically runs checks on your code before each commit to catch issues early.

## Installed Checks

Our pre-commit setup includes:

### 1. Code Formatting
- **Black**: Automatic Python code formatting (line length: 100)
- **isort**: Import statement sorting and organization

### 2. Linting
- **Flake8**: Style guide enforcement with plugins:
  - flake8-docstrings: Docstring conventions
  - flake8-bugbear: Common bug patterns
  - flake8-comprehensions: Better list/dict/set comprehensions
  - flake8-simplify: Code simplification suggestions

### 3. Type Checking
- **mypy**: Static type checking for Python

### 4. Security
- **Bandit**: Security issue detection in Python code
- **Safety**: Dependency vulnerability checking

### 5. General Checks
- Trailing whitespace removal
- End-of-file fixing
- YAML/JSON/TOML validation
- Large file detection
- Merge conflict detection

## Installation

### 1. Install Development Dependencies

From the project root:

```bash
cd backend
source .venv/bin/activate  # Activate your virtual environment
pip install -e ".[dev]"    # Install package with dev dependencies
```

### 2. Install Pre-commit Hooks

From the project root (not backend directory):

```bash
cd /Users/mac/Desktop/code-open/hostagent  # Project root
pre-commit install
```

This will install the git hooks in your repository.

### 3. Verify Installation

```bash
pre-commit --version
```

You should see the pre-commit version number.

## Usage

### Automatic Running

Once installed, pre-commit hooks will **automatically run** on every `git commit`:

```bash
git add .
git commit -m "Your commit message"
# Pre-commit hooks will run automatically here
```

If any hook fails:
- The commit will be blocked
- Files may be automatically fixed (formatting)
- You'll see error messages for issues that need manual fixing

### Manual Running

Run checks on all files:

```bash
pre-commit run --all-files
```

Run checks on specific files:

```bash
pre-commit run --files backend/src/deepagents/graph.py
```

Run a specific hook:

```bash
pre-commit run black --all-files
pre-commit run flake8 --all-files
pre-commit run mypy --all-files
```

### Skipping Hooks (Not Recommended)

In emergencies only, you can skip hooks:

```bash
git commit --no-verify -m "Emergency fix"
```

**Warning**: This bypasses all quality checks. Use sparingly.

## Common Workflows

### First Time Setup

```bash
# 1. Install dependencies
cd backend
pip install -e ".[dev]"

# 2. Install pre-commit hooks (from project root)
cd ..
pre-commit install

# 3. Run on all files to fix initial issues
pre-commit run --all-files

# 4. Review and commit any auto-fixes
git add .
git commit -m "chore: apply pre-commit formatting"
```

### Daily Development

```bash
# Make your changes
vim backend/src/deepagents/my_file.py

# Stage changes
git add backend/src/deepagents/my_file.py

# Commit (hooks run automatically)
git commit -m "feat: add new feature"

# If hooks fail and auto-fix:
git add .  # Stage the auto-fixes
git commit -m "feat: add new feature"  # Commit again
```

### Updating Hooks

```bash
# Update to latest hook versions
pre-commit autoupdate

# Re-run on all files
pre-commit run --all-files
```

## Configuration Files

### `.pre-commit-config.yaml` (project root)
Main pre-commit configuration defining all hooks.

### `backend/.flake8`
Flake8 linting rules and exclusions.

### `backend/pyproject.toml`
Configuration for Black, isort, mypy, bandit, and pytest.

## Troubleshooting

### Hook Installation Failed

```bash
# Remove and reinstall
pre-commit uninstall
pre-commit clean
pre-commit install
```

### Hooks Not Running

```bash
# Check if hooks are installed
ls -la .git/hooks/pre-commit

# Reinstall if missing
pre-commit install
```

### Black and Flake8 Conflicts

Our configuration is designed to avoid conflicts:
- Black line length: 100
- Flake8 max line length: 100
- Flake8 ignores: E203, W503, E501 (Black-compatible)

### Mypy Import Errors

If mypy complains about missing imports:

```bash
# Install type stubs
pip install types-redis types-requests

# Or ignore specific imports in pyproject.toml
# Already configured: ignore_missing_imports = true
```

### Performance Issues

If pre-commit is slow:

```bash
# Run hooks in parallel (default)
# Check hook configuration for --parallel option

# Skip slow hooks for quick commits
SKIP=mypy,bandit git commit -m "Quick fix"
```

## Best Practices

1. **Run locally before pushing**: Always test your changes locally
2. **Don't skip hooks**: They catch real issues early
3. **Fix root causes**: Don't just silence warnings
4. **Keep dependencies updated**: Run `pre-commit autoupdate` monthly
5. **Review auto-fixes**: Black and isort will modify your code - review changes

## CI Integration

Pre-commit hooks should also run in CI:

```yaml
# .github/workflows/pre-commit.yml
name: Pre-commit
on: [push, pull_request]
jobs:
  pre-commit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - uses: pre-commit/action@v3.0.0
```

## Quick Reference

```bash
# Install hooks
pre-commit install

# Run all hooks
pre-commit run --all-files

# Run specific hook
pre-commit run black --all-files

# Update hooks
pre-commit autoupdate

# Uninstall
pre-commit uninstall

# Skip hooks (emergency only)
git commit --no-verify
```

## Getting Help

- Pre-commit docs: https://pre-commit.com/
- Black docs: https://black.readthedocs.io/
- Flake8 docs: https://flake8.pycqa.org/
- mypy docs: https://mypy.readthedocs.io/
- Bandit docs: https://bandit.readthedocs.io/

## Questions?

Check the project's CLAUDE.md for more information or ask the team.
