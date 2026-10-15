#!/usr/bin/env python3
"""Run real skill checks, bind the report to their inputs, or verify that report."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ['SKILL.md', 'README.md', '.gitignore', 'references/retrospective-one.md',
          'references/retrospective-two.md', 'scripts/check_phase_one.py',
          'scripts/playbook_settings.py', 'scripts/validate_delivery.py',
          'tests/test_check_phase_one.py', 'tests/test_playbook_settings.py',
          'tests/fixtures/phase-one-missing-decision.md', 'evals/trigger_cases.json']
EXPECTED_RESULTS = ['settings_cli', 'structure', 'trigger_heuristic', 'secret_scan']


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--asm-root', type=Path, default=Path.home() / '.agents' / 'skills' / 'asm')
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument('--output', type=Path)
    group.add_argument('--check', type=Path)
    args = p.parse_args()
    base = args.asm_root.resolve() / 'modules' / 'make' / 'scripts'
    hashes = {name: digest(ROOT / name) for name in INPUTS}
    tools = {name: digest(base / name) for name in ['validate_skill.py', 'trigger_eval.py', 'secret_scan.sh']}
    if args.check:
        report = json.loads((ROOT / args.check).read_text(encoding='utf-8'))
        names = [result['name'] for result in report['results']]
        if (report['inputs'] != hashes or report['tools'] != tools
                or names != EXPECTED_RESULTS
                or any(result['exit_code'] for result in report['results'])):
            raise SystemExit('Report stale, incomplete, or a required check failed')
        print('PASS: current input/tool identities and all required command results match')
        return 0
    commands = [
        ('settings_cli', [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py']),
        ('structure', [sys.executable, '-B', str(base / 'validate_skill.py'), '.', '--require-folded-description']),
        ('trigger_heuristic', [sys.executable, '-B', str(base / 'trigger_eval.py'), '.', '--cases', 'evals/trigger_cases.json']),
        ('secret_scan', ['bash', str(base / 'secret_scan.sh'), '.']),
    ]
    results = []
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    for name, command in commands:
        r = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=45)
        output = (r.stdout + r.stderr).replace(str(ROOT), '<skill-root>').replace(str(base), '<asm-checks>')
        results.append({'name': name, 'exit_code': r.returncode, 'output': output})
        print(name, r.returncode)
    report = {'version': 1, 'inputs': hashes, 'tools': tools, 'results': results,
              'limitations': ['Trigger gate is heuristic, not model routing', 'CLI checks do not prove every Agent or platform follows the two-phase protocol']}
    out = ROOT / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return int(any(r['exit_code'] for r in results))


if __name__ == '__main__':
    sys.exit(main())
