"""Unit tests for process_swe_projects.py and test_uniformity.py (stdlib only)."""

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import process_swe_projects as psp  # noqa: E402
import test_uniformity  # noqa: E402

BASE = 'a' * 40
PATCH = 'b' * 40


def make_project(root: Path, name: str, resolved=True, f2p_ok=1, f2p_fail=0,
                 merged=True, gold=True, nested=False, with_report=True) -> Path:
    """Create a synthetic SWE-Bench style project directory."""
    path = root / name
    if nested:
        path = path / name
    path.mkdir(parents=True)
    for d in ('logs', 'results', 'patches', 'envs'):
        (path / d).mkdir()
    (path / f'{name}.json').write_text(json.dumps({
        'task_id': name,
        'instance_id': name,
        'base_commit': BASE,
        'patch_commit': PATCH,
        'merged_time': '2025-01-01T00:00:00Z' if merged else None,
        'difficulty': 'easy',
        'language': 'python',
        'files_changed': ['a.py'],
        'fail_to_pass': ['test_a'],
        'pass_to_pass': ['test_b'],
    }))
    (path / 'agent_patch.diff').write_text('diff')
    if gold:
        (path / 'patches' / 'gold_src.diff').write_text('diff')
        (path / 'patches' / 'gold_test.diff').write_text('diff')
    if with_report:
        (path / 'results' / 'report.json').write_text(json.dumps({
            'resolved': resolved,
            'patch_applied': True,
            'tests_run': True,
            'tests': {
                'FAIL_TO_PASS': {'success': ['t'] * f2p_ok, 'failure': ['t'] * f2p_fail},
                'PASS_TO_PASS': {'success': ['p'], 'failure': []},
            },
        }))
    (path / 'logs' / f'{name}_base.log').write_text('x')
    return path


class ProcessorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_find_project_directories_matches_pattern_and_nesting(self):
        make_project(self.root, 'org__repo-1')
        make_project(self.root, 'org__repo-2', nested=True)
        (self.root / 'not_a_project').mkdir()
        (self.root / 'org__repo-3').mkdir()  # no metadata file
        found = psp.SWEProjectProcessor(str(self.root)).find_project_directories()
        self.assertEqual([p.name for p in found], ['org__repo-1', 'org__repo-2'])
        self.assertEqual(found[1], self.root / 'org__repo-2' / 'org__repo-2')

    def test_derived_outputs_solved(self):
        p = make_project(self.root, 'org__repo-1')
        proc = psp.SWEProjectProcessor(str(self.root))
        derived = proc.derive_outputs(proc.process_project(p))
        self.assertEqual(derived['evaluation_status'], 'SOLVED')
        self.assertEqual(derived['test_execution'], 'COMPLETED')
        self.assertTrue(derived['pr_merged'])
        self.assertTrue(derived['patches_available'])
        self.assertEqual(derived['commit_mapping'], {'base': BASE, 'patch': PATCH})
        self.assertEqual(derived['metrics']['fail_to_pass_count'], '1/1')
        self.assertEqual(derived['metrics']['fail_to_pass_success_rate'], 1.0)

    def test_derived_outputs_partial_and_unsolved(self):
        partial = make_project(self.root, 'org__repo-1', resolved=False, f2p_ok=1, f2p_fail=1)
        unsolved = make_project(self.root, 'org__repo-2', resolved=False, f2p_ok=0, f2p_fail=2,
                                merged=False, gold=False)
        proc = psp.SWEProjectProcessor(str(self.root))
        d1 = proc.derive_outputs(proc.process_project(partial))
        d2 = proc.derive_outputs(proc.process_project(unsolved))
        self.assertEqual(d1['evaluation_status'], 'PARTIALLY_SOLVED')
        self.assertEqual(d1['metrics']['fail_to_pass_success_rate'], 0.5)
        self.assertEqual(d2['evaluation_status'], 'UNSOLVED')
        self.assertFalse(d2['pr_merged'])
        self.assertFalse(d2['patches_available'])

    def test_missing_report_is_not_run(self):
        p = make_project(self.root, 'org__repo-1', with_report=False)
        proc = psp.SWEProjectProcessor(str(self.root))
        derived = proc.derive_outputs(proc.process_project(p))
        self.assertEqual(derived['evaluation_status'], 'UNSOLVED')
        self.assertEqual(derived['test_execution'], 'NOT_RUN')
        self.assertEqual(derived['metrics'], {})

    def test_main_writes_both_files_and_report_statistics(self):
        make_project(self.root, 'org__repo-1')
        make_project(self.root, 'org__repo-2', resolved=False, f2p_ok=0, f2p_fail=1)
        report_file = self.root / 'swe_projects_output.json'
        derived_file = self.root / 'derived_outputs.json'
        cwd = os.getcwd()
        os.chdir(self.root)
        try:
            with redirect_stdout(io.StringIO()) as out:
                psp.main([], str(report_file), str(derived_file))
        finally:
            os.chdir(cwd)
        self.assertIn('Found 2 projects to process', out.getvalue())
        report = json.loads(report_file.read_text())
        self.assertEqual(report['summary']['total_projects'], 2)
        self.assertEqual(report['statistics']['solved'], 1)
        self.assertEqual(report['statistics']['unsolved'], 1)
        self.assertEqual({p['id'] for p in report['projects']}, {'org__repo-1', 'org__repo-2'})
        derived = json.loads(derived_file.read_text())
        self.assertEqual(len(derived['projects']), 2)
        self.assertEqual(test_uniformity.check_uniformity(derived), [])

    def test_main_with_explicit_dirs_and_missing_commits(self):
        p = make_project(self.root, 'org__repo-1')
        meta = p / 'org__repo-1.json'
        meta.write_text(json.dumps({'task_id': 'x'}))  # no commit hashes
        report_file = self.root / 'r.json'
        derived_file = self.root / 'd.json'
        with redirect_stdout(io.StringIO()) as out:
            psp.main([str(p)], str(report_file), str(derived_file))
        self.assertIn('Commits: N/A -> N/A', out.getvalue())
        derived = json.loads(derived_file.read_text())
        self.assertEqual(test_uniformity.check_uniformity(derived), [])


class UniformityTests(unittest.TestCase):
    def good(self):
        return {
            'project_id': 'org__repo-1', 'evaluation_status': 'SOLVED', 'pr_merged': True,
            'patches_available': True, 'test_execution': 'COMPLETED', 'metrics': {},
            'commit_mapping': {'base': BASE, 'patch': PATCH},
        }

    def test_valid_document_passes(self):
        self.assertEqual(test_uniformity.check_uniformity(
            {'timestamp': 't', 'projects': [self.good()]}), [])

    def test_detects_bad_commit_missing_field_bad_status_duplicate(self):
        bad = self.good()
        bad['commit_mapping']['base'] = 'abc'
        bad['evaluation_status'] = 'MAYBE'
        del bad['pr_merged']
        problems = test_uniformity.check_uniformity(
            {'timestamp': 't', 'projects': [self.good(), bad, self.good()]})
        joined = '\n'.join(problems)
        self.assertIn('not a 40-char hex hash', joined)
        self.assertIn("invalid evaluation_status 'MAYBE'", joined)
        self.assertIn("missing required field 'pr_merged'", joined)
        self.assertIn('duplicate project_id', joined)

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'derived_outputs.json'
            path.write_text(json.dumps({'timestamp': 't', 'projects': [self.good()]}))
            with redirect_stdout(io.StringIO()):
                self.assertEqual(test_uniformity.main([str(path)]), 0)
            path.write_text(json.dumps({'timestamp': 't', 'projects': [{}]}))
            with redirect_stdout(io.StringIO()):
                self.assertEqual(test_uniformity.main([str(path)]), 1)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(test_uniformity.main([str(Path(d) / 'missing.json')]), 1)


if __name__ == '__main__':
    unittest.main()
