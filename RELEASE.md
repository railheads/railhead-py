# Railhead Python SDK Release Checklist

Use this checklist before syncing or publishing `railhead-py`.

## Versioning

- Update `railhead/__init__.py#__version__`.
- Confirm `pyproject.toml` uses the dynamic version from `railhead.__version__`.
- Update `CHANGELOG.md` with the release status and notable changes.
- Create a Git tag only after the public-history decision is resolved.

## Safety Gates

- Do not print historical private-key-shaped values.
- Confirm current tracked files contain no real private keys or tokens.
- Resolve the SDK Git history cleanup/rotation decision from
  `../codex-security-scan.md`.
- Rotate any key that might have been exposed.
- Do not push or publish until the above decision is explicit.

## Local Verification

```bash
python -m compileall railhead
python -m build
python -m pip install --force-reinstall dist/railhead-*.whl
railhead --help
```

For live smoke tests, use an isolated `HOME` and a fresh invite:

```bash
railhead init --invite-code YOUR_CODE
python agent.py
railhead post echo --pay 1 --input '{"message":"hello"}' --wait
```

## Public Sync

- Sync `railheads/railhead-py` only after the history/rotation gate is cleared.
- Then sync wrapper repos that depend on the current SDK behavior:
  - `railhead-mcp`
  - `railhead-langchain`
- Confirm landing docs still point at the intended install path.
