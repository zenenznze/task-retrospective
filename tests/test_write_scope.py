import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/check_write_scope.py"


def run_cli(*arguments):
    return subprocess.run([sys.executable, "-B", str(SCRIPT), *map(str, arguments)],
                          capture_output=True, text=True, check=False)


class WriteScopeTests(unittest.TestCase):
    def test_allowed_write_and_protected_overlap(self):
        with tempfile.TemporaryDirectory(prefix="retrospective-scope-") as directory:
            root = Path(directory).resolve()
            protected = root / "frozen"
            protected.mkdir()
            arguments = ("--allow", root, "--protect", protected)
            before = sorted(path.relative_to(root) for path in root.rglob("*"))
            accepted = run_cli(*arguments, "--write", root / "handbook/chapter.md")
            self.assertEqual(accepted.returncode, 0, accepted.stderr)
            for target, reason in ((protected, "protected_overlap"),
                                   (protected / "report.md", "protected_overlap"),
                                   (root, "protected_overlap"),
                                   (root.parent / "outside.md", "outside_allowed_roots")):
                with self.subTest(target=target):
                    rejected = run_cli(*arguments, "--write", target)
                    self.assertEqual(rejected.returncode, 1, rejected.stderr)
                    self.assertIn(reason, [item["reason"] for item in
                                           json.loads(rejected.stdout)["errors"]])
            self.assertEqual(before, sorted(path.relative_to(root) for path in root.rglob("*")))

    def test_relative_paths_and_abbreviated_flags_are_rejected(self):
        relative = run_cli("--allow", ROOT, "--write", "README.md")
        self.assertEqual(relative.returncode, 1)
        self.assertEqual(json.loads(relative.stdout)["errors"][0]["reason"], "invalid_path")
        abbreviated = run_cli("--all", ROOT, "--write", ROOT / "README.md")
        self.assertEqual(abbreviated.returncode, 2)

    def test_alias_cannot_hide_protected_root(self):
        with tempfile.TemporaryDirectory(prefix="retrospective-alias-") as directory:
            root = Path(directory).resolve()
            protected = root / "frozen"
            protected.mkdir()
            marker = protected / "keep.txt"
            marker.write_text("preserve", encoding="utf-8")
            alias = root / "alias"
            if os.name == "nt":
                result = subprocess.run(["cmd", "/c", "mklink", "/J", str(alias),
                                         str(protected)], capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
            else:
                alias.symlink_to(protected, target_is_directory=True)
            try:
                result = run_cli("--allow", root, "--protect", protected,
                                 "--write", alias / "output.md")
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(json.loads(result.stdout)["errors"][0]["reason"],
                                 "protected_overlap")
                self.assertEqual(marker.read_text(encoding="utf-8"), "preserve")
            finally:
                if os.name == "nt":
                    alias.rmdir()
                else:
                    alias.unlink()


if __name__ == "__main__":
    unittest.main()
