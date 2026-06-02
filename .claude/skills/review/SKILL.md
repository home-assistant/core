---
name: review
description: Reviews code changes and provides constructive feedback. Should be used when a review is requested to provide a consistent review behavior and output format. This skill can be used for code reviews in general, not just for GitHub pull requests.
---

# Review Code Changes

## Analyze the code changes for:
- Code quality and style consistency
- Potential bugs or issues
- Performance implications
- Security concerns
- Test coverage
- Documentation updates if needed

## Verification:
- After the review, run parallel subagents for each finding to double check it.
- Spawn up to a maximum of 10 parallel subagents at a time.
- Gather the results from the subagents and summarize them in the final review comments.

## IMPORTANT:
- Just review. DO NOT make any changes.
- Be constructive and specific in your comments.
- Suggest improvements where appropriate.
- Do not comment on code style, formatting, or linting-only issues.
- No need to run tests or linters, just review the code changes.
- No need to highlight things that are already good.

## Output format:
- List specific comments for each file/line that needs attention.
- Reference files using a markdown link whose text is the file name and line number, and whose target is the full relative path including the line number (e.g. `[sensor.py:143](homeassistant/components/example/sensor.py:143)`).
- In the end, summarize with an overall assessment (approve, request changes, or comment) and bullet point list of changes suggested, if any.
  - Example output:
    ```
    Overall assessment: request changes.
    - [CRITICAL] [sensor.py:143](homeassistant/components/example/sensor.py:143) - Memory leak
    - [PROBLEM] [data_processing.py:87](homeassistant/components/example/data_processing.py:87) - Inefficient algorithm
    - [SUGGESTION] [test_init.py:45](tests/components/example/test_init.py:45) - Improve x variable name
    ```
  - Make sure to include the file and line number when possible in the bullet points.
