import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'playbook_settings.py'


class SettingsCLI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'installation'
        (self.root / 'scripts').mkdir(parents=True)
        self.script = self.root / 'scripts' / SCRIPT.name
        shutil.copyfile(SCRIPT, self.script)
        self.target = Path(self.temp.name) / '手册 with spaces'
        self.target.mkdir()
        self.config = self.root / '.local' / 'config.json'

    def call(self, *args, cwd=None, script=None):
        r = subprocess.run([sys.executable, str(script or self.script), *args], cwd=cwd,
                           capture_output=True, text=True)
        return r.returncode, json.loads(r.stdout)

    def test_missing_read_creates_no_settings(self):
        code, result = self.call('get')
        self.assertEqual(code, 0)
        self.assertEqual(result['status'], 'needs_target')
        self.assertFalse((self.root / '.local').exists())

    def test_cross_process_directory_and_discovery_link(self):
        self.assertEqual(self.call('set', '--target', str(self.target))[0], 0)
        link = Path(self.temp.name) / 'discovery'
        link.symlink_to(self.root, target_is_directory=True)
        code, result = self.call('get', cwd=self.target, script=link / 'scripts' / SCRIPT.name)
        self.assertEqual(code, 0)
        self.assertEqual(result['target'], str(self.target))
        self.assertEqual(result['source'], 'saved')
        self.assertEqual(self.call('get', '--target', '')[1]['target'], str(self.target))
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o600)
        self.assertFalse((self.root / '.local' / 'settings.lock').exists())

    def test_override_does_not_change_default_and_replace_is_explicit(self):
        other = str(Path(self.temp.name) / 'second')
        self.call('set', '--target', str(self.target))
        before = self.config.read_bytes()
        self.assertEqual(self.call('get', '--target', other)[1]['source'], 'explicit')
        self.assertEqual(self.config.read_bytes(), before)
        code, result = self.call('set', '--target', other)
        self.assertEqual(code, 2)
        self.assertEqual(result['reason'], 'default_conflict')
        self.assertEqual(self.config.read_bytes(), before)
        self.assertEqual(self.call('set', '--target', other, '--replace')[0], 0)
        self.assertEqual(self.call('get')[1]['target'], other)

    def test_corrupt_config_preserved(self):
        self.config.parent.mkdir()
        self.config.write_text('{broken')
        code, result = self.call('get')
        self.assertEqual(code, 2)
        self.assertEqual(result['reason'], 'invalid_config')
        self.assertEqual(self.call('set', '--target', str(self.target))[1]['reason'], 'invalid_config')
        self.assertEqual(self.config.read_text(), '{broken')

    def test_invalid_inputs_and_credential_url_rejected(self):
        for target in ['', 'relative/path', 'https://user:example-secret@example.test/repo', 'https://example.test/repo?x=1', 'https://', 'ssh://example.test', 'ftp://example.test/repo', '/tmp/example\n']:
            with self.subTest(target=target):
                self.assertEqual(self.call('set', '--target', target)[0], 2)
        self.assertFalse(self.config.exists())

    def test_git_url_persists_without_checkout_or_network(self):
        for target in ['https://example.test/owner/handbook.git', 'gitea:owner/handbook.git', 'git@example.test:owner/handbook.git']:
            self.assertEqual(self.call('set', '--target', target, '--replace')[0], 0)
            self.assertEqual(self.call('get')[1]['target'], target)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ['.local', 'scripts'])

    def test_busy_lock_and_symlink_preserve_other_resources(self):
        self.config.parent.mkdir()
        lock = self.config.parent / 'settings.lock'
        lock.write_text('other writer')
        code, result = self.call('set', '--target', str(self.target))
        self.assertEqual(code, 2)
        self.assertEqual(result['reason'], 'config_busy')
        self.assertEqual(lock.read_text(), 'other writer')
        lock.unlink()
        victim = Path(self.temp.name) / 'other-file'
        victim.write_text('keep')
        self.config.symlink_to(victim)
        self.assertEqual(self.call('set', '--target', str(self.target))[0], 2)
        self.assertEqual(victim.read_text(), 'keep')

    def test_git_fast_forward_preserves_local_config(self):
        remote = Path(self.temp.name) / 'upstream'
        subprocess.run(['git', 'init', '-q', str(remote)], check=True)
        def git(repo, *args):
            return subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True)
        git(remote, 'config', 'user.name', 'Fixture')
        git(remote, 'config', 'user.email', 'fixture@example.test')
        (remote / '.gitignore').write_text('.local/\n')
        (remote / 'scripts').mkdir()
        shutil.copyfile(SCRIPT, remote / 'scripts' / SCRIPT.name)
        git(remote, 'add', '.')
        git(remote, 'commit', '-qm', 'initial')
        updated = Path(self.temp.name) / 'consumer'
        subprocess.run(['git', 'clone', '-q', str(remote), str(updated)], check=True)
        consumer_script = updated / 'scripts' / SCRIPT.name
        self.assertEqual(self.call('set', '--target', str(self.target), script=consumer_script)[0], 0)
        config = updated / '.local' / 'config.json'
        before = config.read_bytes()
        (remote / 'README.md').write_text('source update\n')
        git(remote, 'add', 'README.md')
        git(remote, 'commit', '-qm', 'update source')
        git(updated, 'fetch', 'origin')
        git(updated, 'merge', '--ff-only', '@{upstream}')
        self.assertEqual(config.read_bytes(), before)
        self.assertEqual(self.call('get', script=consumer_script)[1]['target'], str(self.target))
        self.assertEqual(git(updated, 'status', '--porcelain').stdout, b'')

    def test_git_ignored(self):
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        (self.root / '.gitignore').write_text('.local/\n')
        self.call('set', '--target', str(self.target))
        r = subprocess.run(['git', '-C', str(self.root), 'check-ignore', '.local/config.json'], capture_output=True)
        self.assertEqual(r.returncode, 0)


if __name__ == '__main__':
    unittest.main()
