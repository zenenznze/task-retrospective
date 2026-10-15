#!/usr/bin/env python3
"""Check that a phase-one answer carries an explicit capability decision.

Run:
    python3 scripts/check_phase_one.py --answer <answer.md> [--json]
    python3 scripts/check_phase_one.py < answer.md

Reads only the supplied text and writes nothing. It proves that the decision
value, the dedup evidence and the authorization state are present *and
non-empty* in the delivered answer; it does not judge whether the decision
itself is correct, it is not an enforcement gate, and it cannot prove the
answer reached the user.

Accepted shapes, so that the template form and ordinary human renderings are
not rejected:

- a dedicated section at any heading level (``## 能力沉淀决定``, ``### 决定``);
- the template's item-4 list form (``4. 能力沉淀决定：update``);
- bullet lines, bold labels (``- **decision**: `update` ``) or inline text.

Negated mentions (``不应采用 decision: create``) are not read as a decision,
and a present-but-empty ``查重：`` / ``授权：`` value fails closed.
"""

import argparse
import json
import re
import sys

DECISIONS = ('reuse', 'update', 'create', 'record_only', 'do_not_persist')
AUTHORIZATIONS = ('proposal_only', 'explicit_implementation')
SECTION_TITLES = (
    '能力沉淀决定', '能力沉淀判断', '能力沉淀结论', '能力决策', '决定', '决策',
    'capability decision', 'capability-decision', 'decision', 'workflow decision',
)
HEADING = re.compile(r'^(#{1,6})\s*(.+?)\s*$')
# Markers that make a nearby label a description of what must NOT happen.
NEGATIONS = ('不应采用', '不应', '不采用', '不新建', '不需要', '不用', '无需', '不必', '不要', '不可', 'not ', 'no ')
# Only punctuation may sit between a negation marker and the label it negates.
NEGATION_GAP = re.compile(r'^[ \t*_—\-（(【\[，,、；;:：]*$')
DECISION_FIELD = re.compile(r'(?i)(?:能力沉淀)?(?:决定|决策|decision)' + r'[ \t]*[*_]{0,2}[ \t]*[:：][ \t]*[`\'"]*([A-Za-z_][A-Za-z0-9_-]*)')
DEDUP_FIELD = re.compile(r'(?i)(?:查重(?:依据|证据)?|去重|dedup(?:_evidence)?|existing_capabilit\w*|overlap)' + r'[ \t]*[*_]{0,2}[ \t]*[:：][ \t]*([^\n]*)')
AUTHORIZATION_FIELD = re.compile(r'(?i)(?:授权(?:状态)?|authorization|authorisation)' + r'[ \t]*[*_]{0,2}[ \t]*[:：][ \t]*([^\n]*)')
AUTH_TOKEN = re.compile(r'\b(proposal_only|explicit_implementation)\b', re.I)
PLACEHOLDERS = {'todo', 'tbd', '待补', '待填', '待定', 'n/a', 'na', 'none', '空'}


def split_sections(text):
    """Yield (title, body) for every markdown heading block."""
    lines = text.splitlines()
    current_title, buffer = None, []
    for line in lines:
        match = HEADING.match(line)
        if match:
            if current_title is not None:
                yield current_title, '\n'.join(buffer)
            current_title, buffer = match.group(2), []
        elif current_title is not None:
            buffer.append(line)
    if current_title is not None:
        yield current_title, '\n'.join(buffer)


def find_section(text):
    """Return (title, body): every matching heading block, or the whole text.

    Concatenating all matching blocks keeps a filled ``### 决定`` child from
    being hidden behind an empty ``## 能力沉淀决定`` parent.
    """
    matched = [(title, body) for title, body in split_sections(text)
               if any(candidate in title.lower() for candidate in SECTION_TITLES)]
    if not matched:
        return None, text
    return ' / '.join(title for title, _ in matched), '\n'.join(body for _, body in matched)


def _negated(text, start):
    window = text[max(0, start - 8):start]
    for marker in NEGATIONS:
        index = window.rfind(marker)
        if index >= 0 and NEGATION_GAP.match(window[index + len(marker):]):
            return True
    return False


def _clean_value(raw):
    value = re.split(r'[；;，,。]', raw.split('\n')[0])[0]
    return value.strip(' \t`*_<>[]()（）【】-—').strip()


def _usable(value):
    return bool(value) and value.lower() not in PLACEHOLDERS


def _locate(pattern, body):
    """Return (found, value) for a labelled field, skipping negated mentions."""
    found, value = False, ''
    for match in pattern.finditer(body):
        if _negated(body, match.start()):
            continue
        found = True
        value = _clean_value(match.group(1))
        if value:
            break
    return found, value


def check(text):
    errors = []
    title, body = find_section(text)
    if title is not None and not body.strip():
        return ['empty_capability_decision_section'], title

    values = []
    for match in DECISION_FIELD.finditer(body):
        if _negated(body, match.start()):
            continue
        values.append(match.group(1).lower())
    if title is None and not values:
        # No decision heading and no decision field anywhere: the answer simply
        # never delivered the capability decision.
        return ['missing_capability_decision_section'], None
    if not values:
        errors.append('missing_decision_field')
        value = None
    else:
        invalid = [candidate for candidate in values if candidate not in DECISIONS]
        if invalid:
            errors.append('invalid_decision_value:' + invalid[0])
            value = invalid[0]
        elif len(set(values)) > 1:
            errors.append('ambiguous_decision_field:' + ','.join(sorted(set(values))))
            value = None
        else:
            value = values[0]

    found, dedup_value = _locate(DEDUP_FIELD, body)
    if not found:
        errors.append('missing_dedup_evidence')
    elif not _usable(dedup_value):
        errors.append('empty_dedup_evidence')

    found, auth_value = _locate(AUTHORIZATION_FIELD, body)
    if not found:
        errors.append('missing_authorization_state')
    elif not _usable(auth_value):
        errors.append('empty_authorization_state')
    elif not AUTH_TOKEN.search(auth_value):
        errors.append('invalid_authorization_state:' + auth_value)

    return errors, value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--answer', help='File holding the phase-one answer text; omit to read stdin')
    parser.add_argument('--json', action='store_true', help='Machine-readable output only')
    args = parser.parse_args(argv)
    if args.answer:
        try:
            text = open(args.answer, encoding='utf-8').read()
        except OSError as error:
            print(json.dumps({'result': 'FAIL', 'errors': ['unreadable_answer:' + str(error)]}, ensure_ascii=False))
            return 2
    else:
        text = sys.stdin.read()
    errors, value = check(text)
    report = {
        'result': 'FAIL' if errors else 'PASS',
        'errors': errors,
        'decision': value,
        'scope': ('non-empty capability decision, dedup evidence and authorization state in the supplied text; '
                  'not judgement quality, not runtime enforcement, and not proof that the answer reached the user'),
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(('PASS' if not errors else 'FAIL') + ': ' + ('phase-one capability decision present' if not errors else ', '.join(errors)))
        print('scope: ' + report['scope'])
    return int(bool(errors))


if __name__ == '__main__':
    sys.exit(main())
