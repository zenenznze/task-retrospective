"""Check candidate completeness and stage-one boundary with the actual CLI."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

CLI=Path(__file__).resolve().parents[1]/'scripts/check_workflow_candidate.py'


class WorkflowCandidateTests(unittest.TestCase):
    def test_candidate_and_implementation_boundary(self):
        record={'decision':'create','job':'素材包准备','inputs':['字幕','原素材'],'outputs':['提示词','片段'],'exclusions':['接管执行现场'],'evidence':['实际交付与越界更新证据'],'existing_capabilities':['封面生成负责图像，未覆盖制作包'],'mechanisms':['显式写集与移交拒绝'],'owner_after_handoff':'执行Agent','validation':['真实CLI截取与范围拒绝'],'authorization':'proposal_only'}
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'candidate.json'
            file.write_text(json.dumps(record,ensure_ascii=False),encoding='utf-8')
            def run(extra=()):
                return subprocess.run([sys.executable,str(CLI),'--record',str(file),*extra],capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(run().returncode,0)
            self.assertNotEqual(run(['--require-implementation']).returncode,0)
            record['authorization']='explicit_implementation'
            file.write_text(json.dumps(record,ensure_ascii=False),encoding='utf-8')
            self.assertEqual(run(['--require-implementation']).returncode,0)
            del record['owner_after_handoff']
            file.write_text(json.dumps(record,ensure_ascii=False),encoding='utf-8')
            result=run()
            self.assertNotEqual(result.returncode,0)
            self.assertIn('missing_owner_after_handoff',result.stdout)


if __name__=='__main__':
    unittest.main()
