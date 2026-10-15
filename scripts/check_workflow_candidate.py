#!/usr/bin/env python3
"""Validate a workflow-skill candidate without authorizing implementation.
Run: python scripts/check_workflow_candidate.py --record candidate.json [--require-implementation]
Requires Python 3; reads only the specified JSON, writes nothing.
"""
import argparse
import json
from pathlib import Path
import sys


def validate(record, require_implementation=False):
    errors=[]
    if not isinstance(record,dict):
        return ['record_must_be_object']
    if record.get('decision') not in {'reuse','update','create','record_only','do_not_persist'}:
        errors.append('invalid_decision')
    for field in ['job','inputs','outputs','exclusions','evidence','existing_capabilities','mechanisms','owner_after_handoff','validation']:
        value=record.get(field)
        if not isinstance(value,(str,list,dict)) or not value or (isinstance(value,str) and not value.strip()):
            errors.append('missing_'+field)
    if record.get('authorization') not in {'proposal_only','explicit_implementation'}:
        errors.append('invalid_authorization')
    if require_implementation and record.get('authorization')!='explicit_implementation':
        errors.append('implementation_not_authorized')
    return errors


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__,allow_abbrev=False)
    parser.add_argument('--record',type=Path,required=True)
    parser.add_argument('--require-implementation',action='store_true')
    args=parser.parse_args(argv)
    try:
        errors=validate(json.loads(args.record.read_text(encoding='utf-8')),args.require_implementation)
    except (OSError,ValueError) as error:
        errors=['invalid_record:'+str(error)]
    print(json.dumps({'result':'FAIL' if errors else 'PASS','errors':errors,'scope':'field completeness and declared phase only; not semantic validation or write permission'},ensure_ascii=False))
    return int(bool(errors))


if __name__=='__main__':
    sys.exit(main())
