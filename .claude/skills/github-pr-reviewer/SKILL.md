---
name: github-pr-reviewer
description: Review a GitHub pull request and provide feedback comments. Use when the user says "review the current PR" or asks to review a specific PR.
---

# Review GitHub Pull Request

## Preparation:
- Check if the local commit matches the last one in the PR. If not, checkout the PR locally using 'gh pr checkout'. 
- CRITICAL: If 'gh pr checkout' fails for ANY reason, you MUST immediately STOP.
    - Do NOT attempt any workarounds. 
    - Do NOT proceed with the review.
    - ALERT about the failure and WAIT for instructions.
    - This is a hard requirement - no exceptions.

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
