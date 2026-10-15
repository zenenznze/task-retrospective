#!/usr/bin/env python3
"""Read/save this skill installation's local handbook target; never create it."""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


class SettingsError(ValueError):
    def __init__(self, code, action):
        self.code = code
        self.action = action
        super().__init__(code)


def invalid_target():
    return SettingsError('invalid_target', 'Provide an absolute directory or a credential-free Git address')


def validate_target(value):
    if not isinstance(value, str) or not value.strip() or any(ord(c) < 32 for c in value):
        raise invalid_target()
    value = value.strip()
    if re.match(r'^[A-Za-z]:[\\/]', value) and os.name != 'nt':
        raise SettingsError('platform_mismatch', 'Use a local path for this installation platform')
    if value.startswith('~') or Path(value).is_absolute():
        p = Path(value).expanduser()
        if not p.is_absolute():
            raise invalid_target()
        p = p.resolve()
        if p.exists() and not p.is_dir():
            raise SettingsError('target_not_directory', 'Choose a directory; preserve the existing file')
        return str(p)
    url = urlsplit(value)
    if '://' in value:
        if url.password or (url.scheme != 'ssh' and url.username) or url.query or url.fragment:
            raise SettingsError('unsafe_git_address', 'Remove credentials, queries and fragments before saving')
        if url.scheme not in ('https', 'http', 'ssh') or not url.hostname or not url.path.strip('/'):
            raise invalid_target()
        return value
    if re.fullmatch(r'(?:[A-Za-z0-9_.-]+@)?[A-Za-z0-9_.-]+:[^\s?#]+', value):
        return value
    raise invalid_target()


def config_path():
    folder = ROOT / '.local'
    path = folder / 'config.json'
    if folder.is_symlink() or path.is_symlink():
        raise SettingsError('unsafe_config_link', 'Inspect the link; preserve its target and existing settings')
    return path


def read_settings():
    path = config_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or set(data) != {'version', 'HUMAN_AGENT_PLAYBOOK_TARGET'} or data['version'] != 1:
            raise ValueError('invalid schema')
        data['HUMAN_AGENT_PLAYBOOK_TARGET'] = validate_target(data['HUMAN_AGENT_PLAYBOOK_TARGET'])
    except ValueError as exc:
        raise SettingsError('invalid_config', 'Inspect and repair configuration with the user; preserve the original file') from exc
    return data


def resolve_target(explicit=None):
    # Current explicit input overrides saved defaults without modifying them.
    if explicit and explicit.strip():
        return {'status': 'ready', 'source': 'explicit', 'target': validate_target(explicit)}
    saved = read_settings()
    if saved is None:
        return {'status': 'needs_target', 'source': 'unconfigured', 'target': None}
    target = saved['HUMAN_AGENT_PLAYBOOK_TARGET']
    return {'status': 'ready', 'source': 'saved', 'target': target}


def save_target(target, replace=False):
    target = validate_target(target)
    path = config_path()
    path.parent.mkdir(mode=0o700, exist_ok=True)
    lock = path.parent / 'settings.lock'
    try:
        fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise SettingsError('config_busy', 'Inspect the existing writer or stale lock; do not remove an unknown lock') from exc
    temporary = None
    try:
        os.close(fd)
        old = read_settings()
        if old and old['HUMAN_AGENT_PLAYBOOK_TARGET'] != target and not replace:
            raise SettingsError('default_conflict', 'Use --replace only after the user explicitly changes the default')
        if old and old['HUMAN_AGENT_PLAYBOOK_TARGET'] == target:
            return {'status': 'ready', 'source': 'saved', 'target': target, 'changed': False}
        fd, temporary = tempfile.mkstemp(prefix='config-', suffix='.tmp', dir=path.parent)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump({'version': 1, 'HUMAN_AGENT_PLAYBOOK_TARGET': target}, f, ensure_ascii=False, indent=2)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, path)
        temporary = None
        return {'status': 'ready', 'source': 'saved', 'target': target, 'changed': True}
    finally:
        if temporary:
            Path(temporary).unlink()
        lock.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    read = sub.add_parser('get')
    read.add_argument('--target', default='', help='explicit per-call override; empty reuses saved target')
    save = sub.add_parser('set')
    save.add_argument('--target', required=True)
    save.add_argument('--replace', action='store_true', help='requires user authorization to change the saved default')
    args = parser.parse_args()
    try:
        result = resolve_target(args.target) if args.command == 'get' else save_target(args.target, args.replace)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except SettingsError as exc:
        result = {'status': 'blocked', 'reason': exc.code, 'action': exc.action}
    except PermissionError:
        result = {'status': 'blocked', 'reason': 'permission_denied', 'action': 'Check installation access; do not elevate automatically'}
    except (ValueError, OSError):
        result = {'status': 'blocked', 'reason': 'settings_io_error', 'action': 'Inspect input and installation access; preserve existing settings'}
    # Stable reasons reveal no raw config, credential, path or URL on failure.
    print(json.dumps(result))
    return 2


if __name__ == '__main__':
    sys.exit(main())
