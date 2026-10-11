"""Write the artifact the agentic stage consumes.

The output directory holds:

- `results.json`: the skip decision, the pull request number and head SHA, the
  change counts and the touched domains.
- `pr-meta.json`: the pull request metadata.
- `domains.txt`: one touched domain with a `quality_scale.yaml` per line.
- `pr-diff.patch`: the unified diff of the pull request.
- `rules-index.txt`: one `tier | rule | title` line per quality scale rule.
- `rules/<rule>.md`: the documentation page of every quality scale rule.

The last three are written only for a pull request that is reviewed.
"""

import json
from pathlib import Path
from typing import Any

from .models import PullRequest, Results, RuleDoc


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write a JSON payload, formatted the way the artifact ships it."""
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def write_pull_request(output: Path, results: Results, pr: PullRequest) -> None:
    """Write the files present whether or not the pull request is reviewed."""
    output.mkdir(parents=True, exist_ok=True)
    _write_json(output / "results.json", results.to_dict())
    _write_json(output / "pr-meta.json", pr.to_meta_dict())
    (output / "domains.txt").write_text(
        "".join(f"{domain}\n" for domain in results.domains), encoding="utf-8"
    )


def write_diff(output: Path, diff: str) -> None:
    """Write the unified diff of the pull request."""
    (output / "pr-diff.patch").write_text(diff, encoding="utf-8")


def write_rules(output: Path, index: str, docs: list[RuleDoc]) -> None:
    """Write the rules index and one file per rule documentation page."""
    (output / "rules-index.txt").write_text(index, encoding="utf-8")
    rules_dir = output / "rules"
    rules_dir.mkdir(exist_ok=True)
    for doc in docs:
        (rules_dir / doc.filename).write_text(doc.text, encoding="utf-8")
