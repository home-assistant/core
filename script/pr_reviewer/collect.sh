#!/usr/bin/env bash
# Collects what the PR reviewer workflow needs for one pull request and decides
# whether to review it, in task.json.
#
# Usage: collect.sh <pr-number> <out-dir> [<head-sha>]
# Needs GH_TOKEN and GITHUB_REPOSITORY. <head-sha> pins the commit to review;
# it defaults to the pull request's head.
#
# The workflow keeps no state of its own and reads it back from the pull request:
# its reviews carry gh-aw's hidden marker, and its last review's commit is the
# reviewed head.

set -euo pipefail

PR_NUMBER=$1
OUT=$2
HEAD_SHA=${3:-}
REPO=${GITHUB_REPOSITORY}
BOT='github-actions[bot]'
# Part of the hidden marker gh-aw adds to this workflow's review bodies.
MARKER='workflow_id: pr-reviewer,'
MAX_CHANGED_LINES=5000
MAX_CHANGED_FILES=100

list() {
  gh api --paginate --slurp "$1" | jq 'add // []'
}
# The pull request's diff between $1 and $2, as GitHub shows it, without test snapshots.
pr_diff() {
  gh api -H "Accept: application/vnd.github.diff" "repos/${REPO}/compare/$1...$2" \
    | awk '/^diff --git / { snapshot = ($0 ~ /\.ambr$/) } !snapshot'
}
# The pull request's diff from the per-file patches in $FILES, for when GitHub refuses the whole diff.
files_diff() {
  jq -r '.[] | select(.patch) | (.previous_filename // .filename) as $old
    | "diff --git a/\($old) b/\(.filename)\n--- a/\($old)\n+++ b/\(.filename)\n\(.patch)"' <<< "${FILES}"
}
# Ignores line numbers and blob IDs, so the same changes on a newer base match.
diff_id() {
  grep -v '^index ' "$1" | sed -E 's/^@@ -[0-9,]+ \+[0-9,]+ @@.*/@@/' | sha256sum | cut -d' ' -f1
}
nothing() {
  jq -n --arg reason "$1" '{review: false, reviewed_head: null, reason: $reason}' > "${OUT}/task.json"
  exit 0
}

mkdir -p "${OUT}"
if ! PR=$(gh api "repos/${REPO}/pulls/${PR_NUMBER}" 2> "${OUT}/error.txt"); then
  grep -q 'HTTP 404' "${OUT}/error.txt" || { cat "${OUT}/error.txt" >&2; exit 1; }
  rm -f "${OUT}/error.txt"
  nothing "#${PR_NUMBER} is not a pull request"
fi
rm -f "${OUT}/error.txt"
jq -e --arg repo "${REPO}" \
  '.state == "open" and (.draft | not) and .base.ref == "dev" and .base.repo.full_name == $repo' \
  <<< "${PR}" > /dev/null \
  || nothing "#${PR_NUMBER} isn't an open, non-draft pull request to dev"
jq -e 'any(.labels[]; .name == "pr-reviewer-muted") | not' <<< "${PR}" > /dev/null \
  || nothing "#${PR_NUMBER} is muted with the pr-reviewer-muted label"
CURRENT_HEAD=$(jq -r '.head.sha' <<< "${PR}")
HEAD_SHA=${HEAD_SHA:-${CURRENT_HEAD}}
BASE=$(jq -r '.base.ref' <<< "${PR}")

jq --arg head "${HEAD_SHA}" '{number, title, body, author: .user.login, head_sha: $head,
    head_repo: .head.repo.full_name, base: .base.ref, labels: [.labels[].name],
    additions, deletions, changed_files}' \
  <<< "${PR}" > "${OUT}/pr.json"

list "repos/${REPO}/pulls/${PR_NUMBER}/reviews?per_page=100" \
  | jq --arg bot "${BOT}" --arg marker "${MARKER}" '[.[] | {
      id, user: .user.login, user_type: .user.type, state, commit_id, submitted_at, body,
      ours: (.user.login == $bot and ((.body // "") | contains($marker)))}]' \
  > "${OUT}/reviews.json"
OUR_REVIEWS=$(jq -c '[.[] | select(.ours) | .id]' "${OUT}/reviews.json")

# Replies always point at the first comment of their thread, which names the thread.
list "repos/${REPO}/pulls/${PR_NUMBER}/comments?per_page=100" \
  | jq --arg bot "${BOT}" --argjson our_reviews "${OUR_REVIEWS}" '
      [.[] | {
        id, thread: (.in_reply_to_id // .id), review_id: .pull_request_review_id,
        user: .user.login, user_type: .user.type, path, line, start_line, side,
        original_line, commit_id, original_commit_id, created_at, body, url: .html_url}]
      | map(. + {ours: (.user == $bot and (.review_id | IN($our_reviews[])))})' \
  > "${OUT}/review-comments.json"

gh api graphql --paginate -F owner="${REPO%/*}" -F name="${REPO#*/}" -F number="${PR_NUMBER}" \
  -f query='query($owner: String!, $name: String!, $number: Int!, $endCursor: String) {
    repository(owner: $owner, name: $name) { pullRequest(number: $number) {
      reviewThreads(first: 100, after: $endCursor) {
        nodes { isResolved isOutdated resolvedBy { login } comments(first: 1) { nodes { databaseId } } }
        pageInfo { hasNextPage endCursor }
      }
    } }
  }' \
  --jq '.data.repository.pullRequest.reviewThreads.nodes[]
    | {thread: .comments.nodes[0].databaseId, resolved: .isResolved, outdated: .isOutdated,
       resolved_by: .resolvedBy.login}' \
  | jq -s . > "${OUT}/threads.json"

list "repos/${REPO}/issues/${PR_NUMBER}/comments?per_page=100" \
  | jq '[.[] | {id, user: .user.login, user_type: .user.type, created_at, body, url: .html_url}]' \
  > "${OUT}/issue-comments.json"

FILES=$(list "repos/${REPO}/pulls/${PR_NUMBER}/files?per_page=100" \
  | jq '[.[] | select(.filename | endswith(".ambr") | not)]')
CHANGED_LINES=$(jq '[.[] | .additions + .deletions] | add // 0' <<< "${FILES}")
CHANGED_FILES=$(jq 'length' <<< "${FILES}")
REVIEWED_HEAD=$(jq -r '[.[] | select(.ours)] | sort_by(.submitted_at) | last | .commit_id // ""' "${OUT}/reviews.json")

if ! pr_diff "${BASE}" "${HEAD_SHA}" > "${OUT}/pr.diff"; then
  echo "::notice title=Diff from per-file patches::GitHub refused the diff of #${PR_NUMBER}"
  files_diff > "${OUT}/pr.diff"
fi

REVIEW=true
if [ "${HEAD_SHA}" != "${CURRENT_HEAD}" ]; then
  # Reviewing the older commit after the newer one would make it the reviewed head.
  echo "::notice title=No new review::#${PR_NUMBER} moved on to ${CURRENT_HEAD}, which its own run reviews"
  REVIEW=false
elif [ "${CHANGED_LINES}" -gt "${MAX_CHANGED_LINES}" ] || [ "${CHANGED_FILES}" -gt "${MAX_CHANGED_FILES}" ]; then
  echo "::notice title=No new review::#${PR_NUMBER} changes ${CHANGED_LINES} lines in ${CHANGED_FILES} files, above the limit of ${MAX_CHANGED_LINES} lines and ${MAX_CHANGED_FILES} files"
  REVIEW=false
elif [ ! -s "${OUT}/pr.diff" ]; then
  echo "::notice title=No new review::No diff for #${PR_NUMBER} outside test snapshots"
  REVIEW=false
elif [ "${REVIEWED_HEAD}" = "${HEAD_SHA}" ]; then
  echo "::notice title=No new review::#${PR_NUMBER} was already reviewed at ${HEAD_SHA}"
  REVIEW=false
elif [ -n "${REVIEWED_HEAD}" ]; then
  # Only dev merged in since the last review: the pull request's diff is unchanged.
  if pr_diff "${BASE}" "${REVIEWED_HEAD}" > "${OUT}/reviewed.diff" \
    && [ "$(diff_id "${OUT}/reviewed.diff")" = "$(diff_id "${OUT}/pr.diff")" ]; then
    echo "::notice title=No new review::The diff of #${PR_NUMBER} is unchanged since ${REVIEWED_HEAD}"
    REVIEW=false
  else
    pr_diff "${REVIEWED_HEAD}" "${HEAD_SHA}" > "${OUT}/since-review.diff" || rm -f "${OUT}/since-review.diff"
  fi
  rm -f "${OUT}/reviewed.diff"
fi

jq -n --argjson review "${REVIEW}" --arg reviewed_head "${REVIEWED_HEAD}" \
  '{review: $review, reviewed_head: (if $reviewed_head == "" then null else $reviewed_head end)}' \
  > "${OUT}/task.json"
