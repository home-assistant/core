"""Fetch the Integration Quality Scale rules from the documentation repository."""

from dataclasses import dataclass
import json
from typing import Any

from . import github_api
from .models import RuleDoc

TIERS = ("bronze", "silver", "gold", "platinum")

_INDEX_HEADER = "# Integration Quality Scale rules: tier | rule | title"

# The tier listing and every rule page in a single request.
_QUERY = """
query {
  repository(owner: "home-assistant", name: "developers.home-assistant") {
    tiers: object(expression: "master:docs/core/integration-quality-scale/_includes/tiers.json") {
      ... on Blob { text }
    }
    rules: object(expression: "master:docs/core/integration-quality-scale/rules") {
      ... on Tree { entries { name object { ... on Blob { text } } } }
    }
  }
}
"""


@dataclass(slots=True, frozen=True)
class QualityScaleDocs:
    """The quality scale documentation, as published for the developer docs."""

    tiers: dict[str, list[str]]
    rules: list[RuleDoc]


def _rule_id(entry: str | dict[str, Any]) -> str:
    """Return the rule id of a tier entry, which may also be a bare rule id."""
    return entry["id"] if isinstance(entry, dict) else entry


def fetch_docs(token: str) -> QualityScaleDocs:
    """Fetch the rules of every tier and their documentation pages."""
    repository = github_api.graphql(_QUERY, token)["repository"]
    tiers = json.loads(repository["tiers"]["text"])
    return QualityScaleDocs(
        tiers={tier: [_rule_id(entry) for entry in tiers[tier]] for tier in TIERS},
        rules=[
            RuleDoc(filename=entry["name"], text=entry["object"]["text"])
            for entry in repository["rules"]["entries"]
            if entry["name"].endswith(".md")
        ],
    )


def build_index(docs: QualityScaleDocs) -> str:
    """Render one `tier | rule | title` line per rule, under a header line."""
    titles = {doc.rule: doc.title for doc in docs.rules}
    lines = [
        f"{tier} | {rule} | {titles.get(rule, '')}"
        for tier in TIERS
        for rule in docs.tiers[tier]
    ]
    return "\n".join([_INDEX_HEADER, *lines]) + "\n"
