#!/usr/bin/env python3
"""Test runner for mcp-manifest-validator.

Runs validate.py against every fixture and asserts the expected exit code
and expected issue codes. Exit 0 only if all assertions pass.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VALIDATE = ROOT / "validate.py"
FIX = ROOT / "tests" / "fixtures"

# (fixture, extra_args, expected_exit, expected_codes_that_must_appear)
CASES = [
    ("valid.json", [], 0, []),
    ("valid_warnings.json", [], 2, ["W002", "W003", "W006", "W008"]),
    ("missing_name.json", [], 1, ["E002"]),
    ("bad_name_format.json", [], 1, ["E003", "E004"]),
    ("non_github_name.json", [], 1, ["E004"]),
    ("missing_description.json", [], 1, ["E005"]),
    ("bad_version.json", [], 1, ["E007"]),
    ("missing_repository.json", [], 1, ["E008"]),
    ("repo_missing_url.json", [], 1, ["E009"]),
    ("missing_packages.json", [], 1, ["E010"]),
    ("package_missing_transport.json", [], 1, ["E011"]),
    ("package_bad_transport.json", [], 1, ["E012"]),
    ("remote_transport_no_url.json", [], 1, ["E013"]),
    ("name_repo_mismatch.json", [], 2, ["W005"]),
    ("invalid.json", [], 1, ["E001"]),
    ("version_mismatch/server.json",
     ["--repo-dir", str(FIX / "version_mismatch")], 2, ["W007"]),
]


def run_case(fixture, extra_args):
    cmd = [sys.executable, str(VALIDATE), str(FIX / fixture), *extra_args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def main() -> int:
    failures = 0
    for fixture, extra_args, expected_exit, expected_codes in CASES:
        code, output = run_case(fixture, extra_args)
        problems = []
        if code != expected_exit:
            problems.append(f"exit={code}, expected {expected_exit}")
        for want in expected_codes:
            if want not in output:
                problems.append(f"missing issue code {want}")
        if problems:
            failures += 1
            print(f"FAIL {fixture}: {'; '.join(problems)}")
            print("---- output ----")
            print(output.strip())
            print("----------------")
        else:
            print(f"ok   {fixture} (exit {code})")
    print(f"\n{len(CASES) - failures}/{len(CASES)} fixtures passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
