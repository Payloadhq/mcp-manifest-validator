# mcp-manifest-validator

**Small software that earns its keep.** — a Payload free utility

A zero-dependency Python CLI that validates an MCP `server.json` manifest
against the key requirements of the official MCP server schema — without
needing the schema file itself.

## Install

Nothing. Python 3.10+ and this repo.

```bash
python3 validate.py server.json
```

## Usage

```bash
# validate a manifest
python3 validate.py server.json

# also cross-check the version against pyproject.toml / package.json
python3 validate.py server.json --repo-dir /path/to/repo

# machine-readable output
python3 validate.py server.json --json
```

Exit codes: `0` = clean, `1` = errors found, `2` = warnings only.

Real output:

```
$ python3 validate.py server.json
WARN  [W006] $: no "license" field (recommended for consumers)
0 error(s), 1 warning(s)
```

## What it checks

**Errors** (exit 1)

| Code | Check |
|------|-------|
| E001 | File is not valid JSON |
| E002 | Missing `name` |
| E003 | `name` doesn't match the official pattern `^[a-zA-Z0-9.-]+/[a-zA-Z0-9._-]+$` |
| E004 | `name` doesn't follow the `io.github.<owner>/<server>` registry convention |
| E005 | Missing `description` (required by the official schema) |
| E006 | Missing `version` |
| E007 | `version` is not semantic versioning |
| E008 | Missing `repository` |
| E009 | Missing `repository.url` |
| E010 | `packages` missing or empty (required for registry publication) |
| E011 | Package entry missing `registryType`, `identifier`, or `transport` |
| E012 | Unknown package `transport.type` (known: stdio, streamable-http, sse) |
| E013 | Remote transport (`streamable-http`, `sse`) without a `url` |

**Warnings** (exit 2)

| Code | Check |
|------|-------|
| W001 | Missing `repository.source` |
| W002 | Unknown `registryType` |
| W003 | Package has no pinned `version` |
| W004 | Package `version` differs from top-level `version` |
| W005 | `name` doesn't match the owner/repo in `repository.url` |
| W006 | No `license` field |
| W007 | Manifest version differs from `pyproject.toml` / `package.json` |
| W008 | No `$schema` field |

Notes on scope, stated plainly:

- The official schema's name pattern is looser than `io.github.*`; this tool
  enforces the `io.github.<owner>/<server>` convention because that is what
  the MCP registry expects for GitHub-published servers.
- The official schema does not pattern-constrain `version`; we require semver
  because registries and package managers expect it.
- `license` and `$schema` are advisory here, not schema requirements.

## Tests

```bash
python3 tests/run_tests.py
```

16 fixtures covering valid, warnings-only, and broken manifests. All must pass.

## What this doesn't do

This is a fast manifest sanity check, not a security or readiness audit. It
doesn't test your server's tools, scan for prompt-injection surface, check
hardening, or verify the package actually installs.

For the full 48-rule scan — tool surface analysis, hardening templates,
stress-test harness, readiness verifier, and CI workflow — see the
**[MCP Launch Readiness Audit](https://payloadtools.gumroad.com/l/mcp-launch-readiness-audit)**
($79) by Payload.

## License

MIT — see [LICENSE](LICENSE). Copyright 2026 Payload.

---

**Payload** — small, sharp tools for developers.
Developer portal: https://payloadhq.github.io/ ·
All products: https://payloadtools.gumroad.com/ ·
Contact: kylers.partners@gmail.com
