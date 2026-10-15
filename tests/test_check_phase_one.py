"""Check the phase-one capability-decision gate against real answer shapes."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / 'scripts' / 'check_phase_one.py'
REGRESSION_FIXTURE = ROOT / 'tests' / 'fixtures' / 'phase-one-missing-decision.md'

WITH_DECISION = """## 最后固定回答

1. 本次任务最大的可避免浪费：按状态码猜测包不存在。
2. 本次最值得跨任务复用的经验：权限面归因与产物身份核对。
3. 只能改一个地方：把发布失败归因从猜测改成按层判断。

## 能力沉淀决定

- decision: `create`
- 查重：dev、asm、gitea 只覆盖相邻环节，没有可复用的 npm 权限归因能力。
- 授权：proposal_only，阶段一不创建文件。
"""


class PhaseOneGateTests(unittest.TestCase):
    def run_cli(self, text, *extra):
        with tempfile.TemporaryDirectory() as directory:
            answer = Path(directory) / 'answer.md'
            answer.write_text(text, encoding='utf-8')
            return subprocess.run(
                [sys.executable, str(CLI), '--answer', str(answer), *extra],
                capture_output=True, text=True, encoding='utf-8',
            )

    def test_observed_regression_is_rejected(self):
        """本次真实遗漏的形状：审计完整但缺少能力沉淀决定。"""
        result = self.run_cli(REGRESSION_FIXTURE.read_text(encoding='utf-8'))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('missing_capability_decision_section', result.stdout)

    def test_complete_decision_passes(self):
        result = self.run_cli(WITH_DECISION)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn('PASS', result.stdout)

    def test_every_closed_vocabulary_value_is_accepted(self):
        for value in ('reuse', 'update', 'create', 'record_only', 'do_not_persist'):
            text = WITH_DECISION.replace('`create`', '`%s`' % value)
            self.assertEqual(self.run_cli(text).returncode, 0, value)

    def test_unknown_decision_value_is_rejected(self):
        text = WITH_DECISION.replace('`create`', '`skip`')
        result = self.run_cli(text)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('invalid_decision_value:skip', result.stdout)

    def test_missing_dedup_and_authorization_are_rejected(self):
        for dropped, expected in (('查重：dev、asm、gitea 只覆盖相邻环节，没有可复用的 npm 权限归因能力。', 'missing_dedup_evidence'),
                                  ('授权：proposal_only，阶段一不创建文件。', 'missing_authorization_state')):
            result = self.run_cli(WITH_DECISION.replace(dropped, ''))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(expected, result.stdout)

    def test_empty_section_is_rejected(self):
        result = self.run_cli(WITH_DECISION.split('## 能力沉淀决定')[0] + '## 能力沉淀决定\n')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('empty_capability_decision_section', result.stdout)

    # --- regressions reproduced from the follow-up retrospective audit ---

    def test_present_but_empty_fields_are_rejected(self):
        """空字段曾通过：关键词在场不等于取值非空。"""
        text = """## 最后固定回答

1. 浪费：无。
2. 经验：无。
3. 只改一处：无。

## 能力沉淀决定

- decision: `update`
- 查重：
- 授权：
"""
        result = self.run_cli(text)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('empty_dedup_evidence', result.stdout)
        self.assertIn('empty_authorization_state', result.stdout)

    def test_keywords_only_without_values_are_rejected(self):
        result = self.run_cli(WITH_DECISION.split('## 能力沉淀决定')[0] + '## 能力沉淀决定\n以后注意。\n')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('missing_decision_field', result.stdout)

    def test_negated_mention_is_not_read_as_a_decision(self):
        """`不应采用 decision: create` 曾被误读为 create。"""
        text = """## 能力沉淀决定

本次结论是不应采用 decision: create，因为已有能力足够。
查重：与 dev 的相邻职责重叠，无需新建。
授权：proposal_only。
"""
        result = self.run_cli(text)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('missing_decision_field', result.stdout)

    def test_template_item_four_form_passes(self):
        """模板自身的第 4 项写法（列表项、无独立标题）必须被接受。"""
        text = """## 最后固定回答

1. 本次任务最大的可避免浪费：按状态码猜测包不存在。
2. 本次最值得跨任务复用的经验：权限面归因。
3. 只能改一个地方：把归因从猜测改成按层判断。
4. 能力沉淀决定：update，查重：与 dev 的相邻环节重叠，但缺少 npm 权限归因；授权：explicit_implementation。

复盘一只形成审计和提案，等待人类阅读，不执行阶段二。
"""
        result = self.run_cli(text)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_nested_heading_and_bold_labels_pass(self):
        text = """## 最后固定回答

3. 只能改一个地方：无。

### 决定

- **decision**: `create`
- **查重**：现有 asm/dev/gitea 都不覆盖 npm 权限归因。
- **授权**：`proposal_only`
"""
        result = self.run_cli(text)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_conflicting_decision_values_are_rejected(self):
        text = WITH_DECISION + '\n- decision: `do_not_persist`\n'
        result = self.run_cli(text)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('ambiguous_decision_field', result.stdout)

    def test_incidental_wording_does_not_negate_the_fields(self):
        """`而非新建；授权：...` 曾被当作否定句而误报 missing_authorization_state。"""
        text = """## 最后固定回答

4. 能力沉淀决定：update（属于修补而非新建），查重：与已有检查器重叠但值校验缺失；授权：explicit_implementation。
"""
        result = self.run_cli(text)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_authorization_must_use_the_closed_vocabulary(self):
        text = WITH_DECISION.replace('授权：proposal_only，阶段一不创建文件。', '授权：pending。')
        result = self.run_cli(text)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('invalid_authorization_state', result.stdout)

    def test_stdin_and_json_modes_agree(self):
        with tempfile.TemporaryDirectory() as directory:
            answer = Path(directory) / 'answer.md'
            answer.write_text(WITH_DECISION, encoding='utf-8')
            via_file = subprocess.run([sys.executable, str(CLI), '--answer', str(answer), '--json'],
                                      capture_output=True, text=True, encoding='utf-8')
            via_stdin = subprocess.run([sys.executable, str(CLI), '--json'],
                                       input=WITH_DECISION, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(via_file.returncode, 0, via_file.stdout)
        self.assertEqual(via_stdin.returncode, 0, via_stdin.stdout)
        self.assertEqual(via_file.stdout, via_stdin.stdout)

    def test_unreadable_answer_exits_two(self):
        result = subprocess.run([sys.executable, str(CLI), '--answer', '/nonexistent/answer.md'],
                                capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 2)


if __name__ == '__main__':
    unittest.main()
