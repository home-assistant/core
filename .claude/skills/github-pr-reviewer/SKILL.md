---
name: github-pr-reviewer
description: Reviews GitHub pull requests and provides feedback comments. This is the top skill to use for reviewing Pull Requests from GitHub.
---

# Review GitHub Pull Request

## Follow these steps:
1. Use 'gh pr view' to get the PR details and description.
2. Use 'gh pr diff' to see all the changes in the PR.
3. Analyze the code changes for:
   - Code quality and style consistency
   - Potential bugs or issues
   - Performance implications
   - Security concerns
   - Test coverage
   - Documentation updates if needed
4. Ensure any existing review comments have been addressed.
5. Generate constructive review comments in the CONSOLE. DO NOT POST TO GITHUB YOURSELF.

## IMPORTANT:
- Just review. DO NOT make any changes
- Be constructive and specific in your comments
- Suggest improvements where appropriate
- Only provide review feedback in the CONSOLE. DO NOT ACT ON GITHUB.
- No need to run tests or linters, just review the code changes.
- No need to highlight things that are already good.

## Output format:
- List specific comments for each file/line that needs attention
- In the end, summarize with an overall assessment (approve, request changes, or comment) and bullet point list of changes suggested, if any.
  - Example output:
    ```
    Overall assessment: request changes.
    - [CRITICAL] Memory leak in homeassistant/components/sensor/my_sensor.py:143
    - [PROBLEM] Inefficient algorithm in homeassistant/helpers/data_processing.py:87
    - [SUGGESTION] Improve variable naming in homeassistant/helpers/config_validation.py:45
    ```
