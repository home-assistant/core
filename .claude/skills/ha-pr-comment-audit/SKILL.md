---
name: ha-pr-comment-audit
description: Audits the review comment threads on a Home Assistant GitHub pull request, flagging unaddressed comments, requests for clarification, and threads whose resolved state doesn't match the code. Use when checking whether PR feedback has been handled, either standalone or as part of a full PR review.
---

# Check Home Assistant PR Review Comments

## Instructions:
- Resolve the PR context first. If a PR number is not given, use 'gh pr view' to identify the current branch's PR.
- Fetch the review comment threads for the PR with their resolved state (e.g. 'gh api graphql' for `reviewThreads`, with `isResolved`, `resolvedBy` and each comment's author and URL).
- Judge each thread against the PR's head commit: addressed (fixed, or no longer applicable because the code changed), not addressed, or waiting for an answer.
- Flag comments that have not been addressed. If the author has replied but has not implemented the suggestion, still flag it and summarize the reply.
- Flag comments for which the author has asked for clarification.
- Flag resolved threads that have not been addressed (resolved prematurely), and say who resolved them.
- Flag unresolved threads that have been addressed (addressed but not resolved), citing the change that addresses them (file and line).
- Generate a summary of the flagged comments, grouped by the categories above, including a link for each comment; for the two resolved-state categories, give each thread as `<comment URL> <resolve|unresolve> <one-line rationale citing the evidence>`. Don't include threads that have been addressed and are resolved.


## IMPORTANT:
- Only provide feedback in the CONSOLE. DO NOT ACT ON GITHUB.
