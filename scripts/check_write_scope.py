#!/usr/bin/env python3
"""Check planned writes against allowed and protected roots without writing files.
Run: python scripts/check_write_scope.py --allow ABS_ROOT --write ABS_FILE.
Requires Python 3; this plan check is not a filesystem sandbox.
"""
import argparse
import json
from pathlib import Path
import sys


def absolute_path(value):
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError("Provide an absolute path: " + str(value))
    return path.resolve()


def overlaps(first, second):
    return first == second or first in second.parents or second in first.parents


def check_scope(allowed, protected, writes):
    errors = []
    for target in writes:
        if not any(root == target or root in target.parents for root in allowed):
            errors.append({"path": str(target), "reason": "outside_allowed_roots"})
        for root in protected:
            if overlaps(root, target):
                errors.append({"path": str(target), "reason": "protected_overlap"})
                break
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--allow", action="append", required=True)
    parser.add_argument("--protect", action="append", default=[])
    parser.add_argument("--write", action="append", required=True)
    args = parser.parse_args(argv)
    try:
        allowed = [absolute_path(value) for value in args.allow]
        protected = [absolute_path(value) for value in args.protect]
        writes = [absolute_path(value) for value in args.write]
        errors = check_scope(allowed, protected, writes)
    except (OSError, RuntimeError, ValueError) as error:
        errors = [{"reason": "invalid_path", "detail": str(error)}]
    print(json.dumps({"result": "FAIL" if errors else "PASS", "errors": errors,
                      "scope": "planned writes only; no OS isolation"}))
    return int(bool(errors))


if __name__ == "__main__":
    sys.exit(main())
