# evals-scripts-infra-build

Evals project infra: a processor that walks SWE-Bench project directories and
derives a uniform JSON summary of PR/commit metadata and test results.

## Prerequisites

- Python 3.6 or higher (standard library only, no third-party dependencies)
- Access to a directory of SWE-Bench project folders named `{org}__{repo}-{issue}`,
  each containing `{project}.json`, `agent_patch.diff`, and `logs/`, `results/`,
  `patches/`, `envs/` subdirectories (a double-nested `{project}/{project}/` layout
  is also detected)

## Running the script

### 1. Process all projects

```sh
cd /path/to/sweprojects
python3 /path/to/process_swe_projects.py
```

Set `SWE_PROJECTS_DIR` to point at the projects directory instead of `cd`-ing into it.

This will:

- Automatically find all projects in the directory
- Process each project to extract PR/commit information
- Generate two output files in the current directory:
  - `swe_projects_output.json` - complete analysis report
  - `derived_outputs.json` - simplified derived outputs

### 2. Process specific projects

```sh
python3 process_swe_projects.py project1_dir project2_dir project3_dir
```

## Output files

1. `swe_projects_output.json` contains:
   - Summary statistics (total, solved, partially solved, unsolved, errors)
   - Per-project evaluation status
   - Test metrics and success rates
   - Commit mappings (base -> patch)
2. `derived_outputs.json` contains:
   - Simplified uniform format for all projects
   - Evaluation status (`SOLVED` / `PARTIALLY_SOLVED` / `UNSOLVED`), PR merge status,
     patch availability
   - Commit hashes (`N/A` when missing) and test execution results
     (`COMPLETED` / `FAILED` / `NOT_RUN`)
3. Console output shows:
   - Processing progress for each project
   - Summary statistics
   - Uniform formatted output for quick review

## Verify output uniformity

```sh
python3 test_uniformity.py            # checks ./derived_outputs.json
python3 test_uniformity.py other.json # or an explicit path
```

This checks that:

- All projects have the same structure (no missing or unexpected fields)
- Commit hashes are valid (40 hex characters) or the `N/A` placeholder
- Status values are drawn from the fixed, consistent sets above
- No `project_id` appears twice

Exit code is 0 when the file is uniform, 1 otherwise.

## Tests

```sh
python3 -m unittest discover -s tests -v
```

## Example output

```
Found 40 projects to process
Processing: project1
...

Report saved to: swe_projects_output.json
Summary:
  - Total projects: 40
  - Solved: 25
  - Partially solved: 3
  - Unsolved: 12
  - Errors: 0

Derived outputs saved to: derived_outputs.json
```
