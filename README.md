Instructions to Run the SWE Project Output Processor

  Prerequisites

  - Python 3.6 or higher
  - Access to the SWE-Bench project directory 

  Running the Script

  1. Process All Projects 

  cd /Users/username/sweprojects
  python3 process_swe_projects.py

  This will:
  - Automatically find all projects in the directory
  - Process each project to extract PR/commit information
  - Generate two output files:
    - swe_projects_output.json - Complete analysis report
    - derived_outputs.json - Simplified derived outputs

  2. Process Specific Projects

  python3 process_swe_projects.py project1_dir project2_dir project3_dir

  Output Files

  After running, you'll get:

  1. swe_projects_output.json - Contains:
    - Summary statistics (total, solved, unsolved)
    - Per-project evaluation status
    - Test metrics and success rates
    - Commit mappings (base → patch)
  2. derived_outputs.json - Contains:
    - Simplified uniform format for all projects
    - Evaluation status, PR merge status, patch availability
    - Commit hashes and test execution results
  3. Console Output - Shows:
    - Processing progress for each project
    - Summary statistics
    - Uniform formatted output for quick review

  Verify Output Uniformity

  To verify that all outputs are uniform:
  python3 test_uniformity.py

  This will check:
  - All projects have the same structure
  - Commit hashes are valid (40 hex characters)
  - No missing required fields
  - Consistent status values

  Example Output

  When you run the script, you'll see:
  Found 40 projects to process
  Processing: project1
  ...

  Report saved to: swe_projects_output.json
  
