#!/usr/bin/env python3
"""
mcp-manifest-validator — validate an MCP server.json manifest.

Checks the key requirements of the official MCP server.json schema
(https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json)
plus registry-publishing conventions, WITHOUT needing the schema file:

  Required (errors):
    - name present, matching the official pattern ^[a-zA-Z0-9.-]+/[a-zA-Z0-9._-]+$
    - name following the io.github.<owner>/<server> registry convention
    - description present (required by the official schema)
    - version present and semver
    - repository present with repository.url
    - packages present and non-empty (required for registry publication)
    - every package entry has registryType, identifier, transport
    - package transport.type is a known type; remote transports declare a url

  Advisory (warnings):
    - repository.source missing, unknown registryType, package version missing
      or differing from the top-level version, name not matching the repo in
      repository.url, no license field, no $schema field, version mismatch
      with pyproject.toml / package.json in --repo-dir

Exit codes: 0 = clean, 1 = errors found, 2 = warnings only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

NAME_PATTERN = re.compile(r"^[a-zA-Z0-9.-]+/[a-zA-Z0-9._-]+$")
GITHUB_NAME_PATTERN = re.compile(r"^io\.github\.([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)$")
SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?$")
GITHUB_URL_PATTERN = re.compile(
    r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?/?$", re.IGNORECASE
)
KNOWN_TRANSPORTS = ("stdio", "streamable-http", "sse")
KNOWN_REGISTRY_TYPES = ("npm", "pypi", "oci", "nuget", "mcpb")
REMOTE_TRANSPORTS = ("streamable-http", "sse")


class Issue:
    def __init__(self, code: str, severity: str, location: str, message: str):
        self.code = code
        self.severity = severity  # "ERROR" or "WARN"
        self.location = location
        self.message = message

    def __str__(self) -> str:
        return f"{self.severity:5} [{self.code}] {self.location}: {self.message}"


def _read_version_from_pyproject(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.search(r'(?m)^\s*version\s*=\s*["\']([^"\']+)["\']', text)
    return m.group(1) if m else None


def _read_version_from_package_json(path: Path) -> str | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    v = data.get("version")
    return v if isinstance(v, str) else None


def validate_manifest(data, repo_dir: Path | None = None) -> list[Issue]:
    issues: list[Issue] = []

    if not isinstance(data, dict):
        return [Issue("E001", "ERROR", "$", "manifest root must be a JSON object")]

    # ---- name -----------------------------------------------------------
    name = data.get("name")
    gh_owner = gh_server = None
    if not isinstance(name, str) or not name:
        issues.append(Issue("E002", "ERROR", "name", 'missing required field "name"'))
    else:
        if not NAME_PATTERN.match(name):
            issues.append(
                Issue("E003", "ERROR", "name",
                      f"{name!r} does not match the official name pattern "
                      r"^[a-zA-Z0-9.-]+/[a-zA-Z0-9._-]+$")
            )
        m = GITHUB_NAME_PATTERN.match(name)
        if not m:
            issues.append(
                Issue("E004", "ERROR", "name",
                      f"{name!r} does not follow the io.github.<owner>/<server> "
                      "registry convention for GitHub-published servers")
            )
        else:
            gh_owner, gh_server = m.group(1), m.group(2)

    # ---- description / version ------------------------------------------
    if not isinstance(data.get("description"), str) or not data.get("description"):
        issues.append(Issue("E005", "ERROR", "description",
                            'missing required field "description"'))
    version = data.get("version")
    if not isinstance(version, str) or not version:
        issues.append(Issue("E006", "ERROR", "version",
                            'missing required field "version"'))
    elif not SEMVER_PATTERN.match(version):
        issues.append(Issue("E007", "ERROR", "version",
                            f"{version!r} is not semantic versioning (x.y.z)"))

    # ---- repository ------------------------------------------------------
    repo = data.get("repository")
    repo_url = None
    if not isinstance(repo, dict):
        issues.append(Issue("E008", "ERROR", "repository",
                            'missing required field "repository"'))
    else:
        repo_url = repo.get("url")
        if not isinstance(repo_url, str) or not repo_url:
            issues.append(Issue("E009", "ERROR", "repository.url",
                                'missing required field "repository.url"'))
        if not isinstance(repo.get("source"), str) or not repo.get("source"):
            issues.append(Issue("W001", "WARN", "repository.source",
                                'missing recommended field "repository.source" '
                                '(e.g. "github")'))

    # ---- name <-> repository.url consistency -----------------------------
    if gh_owner and isinstance(repo_url, str):
        m = GITHUB_URL_PATTERN.search(repo_url)
        if m:
            url_owner, url_repo = m.group(1), m.group(2)
            if url_owner.lower() != gh_owner.lower() or \
               url_repo.lower() != gh_server.lower():
                issues.append(Issue(
                    "W005", "WARN", "name",
                    f"name implies io.github.{gh_owner}/{gh_server} but "
                    f"repository.url points at {url_owner}/{url_repo}"))

    # ---- packages ---------------------------------------------------------
    packages = data.get("packages")
    if not isinstance(packages, list) or not packages:
        issues.append(Issue("E010", "ERROR", "packages",
                            '"packages" must be a non-empty array for registry '
                            "publication"))
    else:
        for i, pkg in enumerate(packages):
            loc = f"packages[{i}]"
            if not isinstance(pkg, dict):
                issues.append(Issue("E011", "ERROR", loc,
                                    "package entry must be an object"))
                continue
            for field in ("registryType", "identifier", "transport"):
                if field not in pkg or pkg[field] in (None, ""):
                    issues.append(Issue("E011", "ERROR", loc,
                                        f'missing required field "{field}"'))
            rt = pkg.get("registryType")
            if isinstance(rt, str) and rt and rt not in KNOWN_REGISTRY_TYPES:
                issues.append(Issue("W002", "WARN", f"{loc}.registryType",
                                    f"unknown registryType {rt!r} "
                                    f"(known: {', '.join(KNOWN_REGISTRY_TYPES)})"))
            pv = pkg.get("version")
            if not isinstance(pv, str) or not pv:
                issues.append(Issue("W003", "WARN", loc,
                                    "package has no pinned \"version\""))
            elif isinstance(version, str) and pv != version:
                issues.append(Issue("W004", "WARN", loc,
                                    f"package version {pv!r} differs from "
                                    f"top-level version {version!r}"))
            transport = pkg.get("transport")
            if isinstance(transport, dict):
                ttype = transport.get("type")
                if ttype not in KNOWN_TRANSPORTS:
                    issues.append(Issue("E012", "ERROR", f"{loc}.transport",
                                        f"unknown transport type {ttype!r} "
                                        f"(known: {', '.join(KNOWN_TRANSPORTS)})"))
                elif ttype in REMOTE_TRANSPORTS and not transport.get("url"):
                    issues.append(Issue("E013", "ERROR", f"{loc}.transport",
                                        f'transport type "{ttype}" requires '
                                        'a "url" field'))

    # ---- advisory ----------------------------------------------------------
    if "license" not in data:
        issues.append(Issue("W006", "WARN", "$",
                            'no "license" field (recommended for consumers)'))
    if "$schema" not in data:
        issues.append(Issue("W008", "WARN", "$",
                            'no "$schema" field pointing at the official schema'))

    # ---- version cross-check with project files -----------------------------
    if repo_dir is not None and isinstance(version, str):
        checked = []
        pyproject = repo_dir / "pyproject.toml"
        if pyproject.is_file():
            pv = _read_version_from_pyproject(pyproject)
            if pv:
                checked.append(("pyproject.toml", pv))
        package_json = repo_dir / "package.json"
        if package_json.is_file():
            pv = _read_version_from_package_json(package_json)
            if pv:
                checked.append(("package.json", pv))
        for fname, pv in checked:
            if pv != version:
                issues.append(Issue(
                    "W007", "WARN", "version",
                    f"manifest version {version!r} differs from {fname} "
                    f"version {pv!r}"))

    return issues


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Validate an MCP server.json manifest.")
    ap.add_argument("manifest", help="path to server.json")
    ap.add_argument("--repo-dir",
                    help="directory holding pyproject.toml/package.json for "
                         "version cross-checks")
    ap.add_argument("--json", action="store_true",
                    help="emit machine-readable JSON instead of text")
    args = ap.parse_args(argv)

    try:
        data = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"ERROR: file not found: {args.manifest}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"ERROR [E001] $: invalid JSON: {exc}", file=sys.stderr)
        print("1 error, 0 warnings", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"ERROR: cannot read {args.manifest}: {exc}", file=sys.stderr)
        return 1

    repo_dir = Path(args.repo_dir) if args.repo_dir else None
    issues = validate_manifest(data, repo_dir)
    errors = [i for i in issues if i.severity == "ERROR"]
    warns = [i for i in issues if i.severity == "WARN"]

    if args.json:
        print(json.dumps({
            "file": args.manifest,
            "errors": [vars(i) for i in errors],
            "warnings": [vars(i) for i in warns],
            "exit_code": 1 if errors else (2 if warns else 0),
        }, indent=2))
    else:
        for issue in issues:
            print(issue)
        print(f"{len(errors)} error(s), {len(warns)} warning(s)")

    if errors:
        return 1
    if warns:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
