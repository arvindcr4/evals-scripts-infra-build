#!/usr/bin/env python3
"""
SWE-Bench Project Output Processor

This script processes SWE-Bench project directories to derive standardized outputs
from PR metadata and commit information. It validates the expected folder structure
and generates a uniform output format for all projects.

Usage:
    python3 process_swe_projects.py [project_dir1] [project_dir2] ...
    python3 process_swe_projects.py  # Process all projects in current directory
                                     # (or $SWE_PROJECTS_DIR if set)
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import re
from datetime import datetime

class SWEProjectProcessor:
    """Process SWE-Bench project directories to extract PR/commit information."""

    EXPECTED_STRUCTURE = {
        'required_files': [
            '{project_name}.json',  # Main metadata file
            'agent_patch.diff',      # AI-generated patch
        ],
        'required_dirs': [
            'logs',     # Test execution logs
            'results',  # Test results
            'patches',  # Gold patches
            'envs',     # Docker environment
        ],
        'log_phases': [
            'base',
            'before',
            'after',
            'post_agent_patch'
        ]
    }

    def __init__(self, base_dir: str = '.'):
        """Initialize processor with base directory."""
        self.base_dir = Path(base_dir)
        self.results = []
        self.errors = []

    def find_project_directories(self) -> List[Path]:
        """Find all valid SWE-Bench project directories."""
        projects = []

        # Pattern: {org}__{repo}-{issue_number}
        pattern = re.compile(r'^[a-zA-Z0-9\-_]+__[a-zA-Z0-9\-_]+-\d+$')

        for item in self.base_dir.iterdir():
            if item.is_dir() and pattern.match(item.name):
                # Check for nested structure (some projects have double nesting)
                nested_path = item / item.name
                if nested_path.exists() and nested_path.is_dir():
                    if self._has_metadata_file(nested_path):
                        projects.append(nested_path)
                elif self._has_metadata_file(item):
                    projects.append(item)

        return sorted(projects)

    def _has_metadata_file(self, path: Path) -> bool:
        """Check if directory has the expected metadata JSON file."""
        json_file = path / f"{path.name}.json"
        return json_file.exists()

    def process_project(self, project_path: Path) -> Optional[Dict]:
        """Process a single project directory and extract outputs."""
        try:
            project_name = project_path.name
            result = {
                'project_id': project_name,
                'path': str(project_path),
                'status': 'processed',
                'outputs': {},
                'validation': {}
            }

            # 1. Load and parse main metadata JSON
            metadata_file = project_path / f"{project_name}.json"
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)

                # Extract key information
                result['pr_info'] = {
                    'task_id': metadata.get('task_id'),
                    'instance_id': metadata.get('instance_id'),
                    'base_commit': metadata.get('base_commit'),
                    'patch_commit': metadata.get('patch_commit'),
                    'merged_time': metadata.get('merged_time'),
                    'difficulty': metadata.get('difficulty'),
                    'language': metadata.get('language'),
                    'files_changed': metadata.get('files_changed', []),
                    'fail_to_pass': metadata.get('fail_to_pass', []),
                    'pass_to_pass': metadata.get('pass_to_pass', [])
                }
            else:
                result['validation']['metadata'] = 'MISSING'

            # 2. Check for patches
            patches_dir = project_path / 'patches'
            if patches_dir.exists():
                result['outputs']['patches'] = {
                    'gold_src': (patches_dir / 'gold_src.diff').exists(),
                    'gold_test': (patches_dir / 'gold_test.diff').exists()
                }

            # 3. Check for agent patch
            agent_patch = project_path / 'agent_patch.diff'
            result['outputs']['agent_patch'] = agent_patch.exists()

            # 4. Process results
            results_file = project_path / 'results' / 'report.json'
            if results_file.exists():
                with open(results_file, 'r') as f:
                    report = json.load(f)
                    result['outputs']['test_results'] = {
                        'resolved': report.get('resolved', False),
                        'patch_applied': report.get('patch_applied', False),
                        'tests_run': report.get('tests_run', False),
                        'fail_to_pass': report.get('tests', {}).get('FAIL_TO_PASS', {}),
                        'pass_to_pass': report.get('tests', {}).get('PASS_TO_PASS', {}),
                        'summary': {
                            'fail_to_pass_count': len(report.get('tests', {}).get('FAIL_TO_PASS', {}).get('success', [])),
                            'fail_to_pass_total': len(report.get('tests', {}).get('FAIL_TO_PASS', {}).get('failure', [])) +
                                                 len(report.get('tests', {}).get('FAIL_TO_PASS', {}).get('success', [])),
                            'pass_to_pass_success': len(report.get('tests', {}).get('PASS_TO_PASS', {}).get('success', [])),
                            'pass_to_pass_total': len(report.get('tests', {}).get('PASS_TO_PASS', {}).get('failure', [])) +
                                                len(report.get('tests', {}).get('PASS_TO_PASS', {}).get('success', []))
                        }
                    }
            else:
                result['outputs']['test_results'] = None

            # 5. Process logs
            logs_dir = project_path / 'logs'
            if logs_dir.exists():
                log_files = {}
                for phase in self.EXPECTED_STRUCTURE['log_phases']:
                    # Try different naming patterns
                    patterns = [
                        f"*{phase}.log",
                        f"*_{phase}.log",
                        f"{project_name.replace('__', '').replace('-', '')}_{phase}.log"
                    ]

                    for pattern in patterns:
                        matches = list(logs_dir.glob(pattern))
                        if matches:
                            log_file = matches[0]
                            log_files[phase] = {
                                'exists': True,
                                'file': log_file.name,
                                'size': log_file.stat().st_size
                            }
                            break
                    else:
                        log_files[phase] = {'exists': False}

                result['outputs']['logs'] = log_files

            # 6. Check tmp directory for intermediate files
            tmp_dir = project_path / 'tmp'
            if tmp_dir.exists():
                tmp_files = [f.name for f in tmp_dir.iterdir() if f.is_file()]
                result['outputs']['tmp_files'] = tmp_files
            else:
                result['outputs']['tmp_files'] = []

            # 7. Validation check
            result['validation']['structure_valid'] = self._validate_structure(project_path)

            return result

        except Exception as e:
            self.errors.append({
                'project': str(project_path),
                'error': str(e)
            })
            return None

    def _validate_structure(self, project_path: Path) -> bool:
        """Validate that project has expected structure."""
        required_items = [
            project_path / 'logs',
            project_path / 'results',
            project_path / 'patches',
            project_path / 'envs'
        ]

        return all(item.exists() for item in required_items)

    def derive_outputs(self, project_data: Dict) -> Dict:
        """Derive standardized outputs from project data."""
        if not project_data:
            return {}

        derived = {
            'project_id': project_data['project_id'],
            'evaluation_status': 'UNSOLVED',  # Default
            'pr_merged': False,
            'patches_available': False,
            'test_execution': 'NOT_RUN',
            'metrics': {}
        }

        # Determine evaluation status
        if project_data.get('outputs', {}).get('test_results'):
            test_results = project_data['outputs']['test_results']
            if test_results.get('resolved'):
                derived['evaluation_status'] = 'SOLVED'
            elif test_results.get('summary', {}).get('fail_to_pass_count', 0) > 0:
                derived['evaluation_status'] = 'PARTIALLY_SOLVED'
            else:
                derived['evaluation_status'] = 'UNSOLVED'

            derived['test_execution'] = 'COMPLETED' if test_results.get('tests_run') else 'FAILED'

            # Calculate success metrics
            f2p_total = test_results['summary'].get('fail_to_pass_total', 0)
            f2p_success = test_results['summary'].get('fail_to_pass_count', 0)

            p2p_total = test_results['summary'].get('pass_to_pass_total', 0)
            p2p_success = test_results['summary'].get('pass_to_pass_success', 0)

            derived['metrics'] = {
                'fail_to_pass_success_rate': f2p_success / f2p_total if f2p_total > 0 else 0,
                'fail_to_pass_count': f"{f2p_success}/{f2p_total}",
                'pass_to_pass_stability': p2p_success / p2p_total if p2p_total > 0 else 1.0
            }

        # Check PR merge status
        if project_data.get('pr_info', {}).get('merged_time'):
            derived['pr_merged'] = True

        # Check patch availability
        if project_data.get('outputs', {}).get('patches'):
            patches = project_data['outputs']['patches']
            derived['patches_available'] = patches.get('gold_src', False) and patches.get('gold_test', False)

        # Add commit mapping
        pr_info = project_data.get('pr_info') or {}
        derived['commit_mapping'] = {
            'base': pr_info.get('base_commit') or 'N/A',
            'patch': pr_info.get('patch_commit') or 'N/A'
        }

        return derived

    def process_all(self, project_dirs: Optional[List[str]] = None) -> Dict:
        """Process all projects and generate report."""
        if project_dirs:
            # Process specified directories
            projects = [Path(d) for d in project_dirs]
        else:
            # Find all projects automatically
            projects = self.find_project_directories()

        print(f"Found {len(projects)} projects to process")

        for project in projects:
            print(f"Processing: {project.name}")
            project_data = self.process_project(project)
            if project_data:
                derived = self.derive_outputs(project_data)
                self.results.append({
                    'raw': project_data,
                    'derived': derived
                })

        return self.generate_report()

    def generate_report(self) -> Dict:
        """Generate comprehensive report of all processed projects."""
        report = {
            'summary': {
                'total_projects': len(self.results),
                'processed': len(self.results),
                'errors': len(self.errors),
                'timestamp': datetime.now().isoformat()
            },
            'statistics': {
                'solved': 0,
                'partially_solved': 0,
                'unsolved': 0,
                'patches_available': 0,
                'pr_merged': 0
            },
            'projects': [],
            'errors': self.errors
        }

        for result in self.results:
            derived = result['derived']

            # Update statistics
            if derived['evaluation_status'] == 'SOLVED':
                report['statistics']['solved'] += 1
            elif derived['evaluation_status'] == 'PARTIALLY_SOLVED':
                report['statistics']['partially_solved'] += 1
            else:
                report['statistics']['unsolved'] += 1

            if derived['patches_available']:
                report['statistics']['patches_available'] += 1
            if derived['pr_merged']:
                report['statistics']['pr_merged'] += 1

            # Add project summary
            report['projects'].append({
                'id': derived['project_id'],
                'status': derived['evaluation_status'],
                'metrics': derived.get('metrics', {}),
                'commits': derived.get('commit_mapping', {}),
                'test_execution': derived.get('test_execution', 'UNKNOWN')
            })

        return report

    def save_report(self, output_file: str = 'swe_projects_output.json'):
        """Save the processing report to a JSON file."""
        report = self.generate_report()

        output_path = Path(output_file)
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\nReport saved to: {output_path}")
        print(f"Summary:")
        print(f"  - Total projects: {report['summary']['total_projects']}")
        print(f"  - Solved: {report['statistics']['solved']}")
        print(f"  - Partially solved: {report['statistics']['partially_solved']}")
        print(f"  - Unsolved: {report['statistics']['unsolved']}")
        print(f"  - Errors: {len(self.errors)}")

        return report

    def print_uniform_output(self):
        """Print uniform output for all projects."""
        print("\n" + "="*80)
        print("UNIFORM OUTPUT - ALL PROJECTS")
        print("="*80)

        for result in self.results:
            derived = result['derived']
            print(f"\n[{derived['project_id']}]")
            print(f"  Status: {derived['evaluation_status']}")
            base = str(derived['commit_mapping'].get('base') or 'N/A')
            patch = str(derived['commit_mapping'].get('patch') or 'N/A')
            print(f"  Commits: {base[:8]} -> {patch[:8]}")
            print(f"  Tests: {derived['metrics'].get('fail_to_pass_count', 'N/A')}")
            print(f"  Success Rate: {derived['metrics'].get('fail_to_pass_success_rate', 0):.1%}")


def main(argv: Optional[List[str]] = None,
         report_file: str = 'swe_projects_output.json',
         derived_file: str = 'derived_outputs.json') -> SWEProjectProcessor:
    """Main entry point."""
    argv = sys.argv[1:] if argv is None else argv
    # Determine projects to process
    if argv:
        # Process specified directories
        project_dirs = argv
        processor = SWEProjectProcessor()
    else:
        # Process all in current directory (or SWE_PROJECTS_DIR if set)
        processor = SWEProjectProcessor(os.environ.get('SWE_PROJECTS_DIR', '.'))
        project_dirs = None

    # Process projects
    report = processor.process_all(project_dirs)

    # Save report
    processor.save_report(report_file)

    # Print uniform output
    processor.print_uniform_output()

    # Save derived outputs to separate file
    derived_outputs = {
        'timestamp': datetime.now().isoformat(),
        'projects': [r['derived'] for r in processor.results]
    }

    with open(derived_file, 'w') as f:
        json.dump(derived_outputs, f, indent=2)

    print(f"\nDerived outputs saved to: {derived_file}")
    return processor


if __name__ == "__main__":
    main()
