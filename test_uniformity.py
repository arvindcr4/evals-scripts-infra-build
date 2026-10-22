#!/usr/bin/env python3
"""
Verify that derived_outputs.json (produced by process_swe_projects.py) is uniform.

Checks:
  - every project has the same top-level structure (required fields present)
  - commit hashes are valid (40 hex characters) or the explicit 'N/A' placeholder
  - status values are drawn from a fixed, consistent set

Usage:
    python3 test_uniformity.py [derived_outputs.json]

Exit status is 0 when all checks pass, 1 otherwise.
"""

import json
import re
import sys
from typing import Dict, List

REQUIRED_FIELDS = {
    'project_id': str,
    'evaluation_status': str,
    'pr_merged': bool,
    'patches_available': bool,
    'test_execution': str,
    'metrics': dict,
    'commit_mapping': dict,
}
VALID_EVALUATION_STATUS = {'SOLVED', 'PARTIALLY_SOLVED', 'UNSOLVED'}
VALID_TEST_EXECUTION = {'COMPLETED', 'FAILED', 'NOT_RUN'}
COMMIT_RE = re.compile(r'^[0-9a-f]{40}$')
COMMIT_PLACEHOLDER = 'N/A'


def check_project(project: Dict) -> List[str]:
    """Return a list of problems found in one derived project entry."""
    problems = []
    pid = project.get('project_id', '<unknown>')

    for field, expected_type in REQUIRED_FIELDS.items():
        if field not in project:
            problems.append(f"{pid}: missing required field '{field}'")
        elif not isinstance(project[field], expected_type):
            problems.append(
                f"{pid}: field '{field}' should be {expected_type.__name__}, "
                f"got {type(project[field]).__name__}")

    extra = set(project) - set(REQUIRED_FIELDS)
    if extra:
        problems.append(f"{pid}: unexpected fields {sorted(extra)}")

    if project.get('evaluation_status') not in VALID_EVALUATION_STATUS:
        problems.append(
            f"{pid}: invalid evaluation_status {project.get('evaluation_status')!r}")
    if project.get('test_execution') not in VALID_TEST_EXECUTION:
        problems.append(
            f"{pid}: invalid test_execution {project.get('test_execution')!r}")

    commits = project.get('commit_mapping') or {}
    for key in ('base', 'patch'):
        value = commits.get(key)
        if value is None:
            problems.append(f"{pid}: commit_mapping missing '{key}'")
        elif value != COMMIT_PLACEHOLDER and not (
                isinstance(value, str) and COMMIT_RE.match(value)):
            problems.append(
                f"{pid}: commit_mapping['{key}'] is not a 40-char hex hash: {value!r}")

    return problems


def check_uniformity(data: Dict) -> List[str]:
    """Return all problems found in a loaded derived_outputs.json document."""
    problems = []
    projects = data.get('projects')
    if not isinstance(projects, list):
        return ["top-level 'projects' must be a list"]
    if 'timestamp' not in data:
        problems.append("top-level 'timestamp' missing")

    seen = set()
    for project in projects:
        if not isinstance(project, dict):
            problems.append(f"project entry is not an object: {project!r}")
            continue
        problems.extend(check_project(project))
        pid = project.get('project_id')
        if pid in seen:
            problems.append(f"{pid}: duplicate project_id")
        seen.add(pid)

    return problems


def main(argv: List[str] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    path = argv[0] if argv else 'derived_outputs.json'

    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        print(f"ERROR: cannot read {path}: {e}")
        return 1

    problems = check_uniformity(data)
    count = len(data.get('projects', []) or [])
    if problems:
        print(f"FAIL: {len(problems)} problem(s) across {count} project(s) in {path}")
        for p in problems:
            print(f"  - {p}")
        return 1

    print(f"OK: {count} project(s) in {path} are uniform")
    return 0


if __name__ == '__main__':
    sys.exit(main())
