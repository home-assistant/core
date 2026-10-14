"""Tests for script.quality_scale_review.rules."""

from collections.abc import Callable
import json
from typing import Any

import pytest

from script.quality_scale_review import rules
from script.quality_scale_review.models import RuleDoc

_TOKEN = "test-token"

type InstallGraphql = Callable[[dict[str, Any]], None]


def _graphql_payload(
    tiers: dict[str, list[Any]], entries: list[dict[str, Any]]
) -> dict[str, Any]:
    """Return a payload shaped like the documentation repository query result."""
    return {
        "repository": {
            "tiers": {"text": json.dumps(tiers)},
            "rules": {"entries": entries},
        }
    }


def _entry(name: str, text: str) -> dict[str, Any]:
    """Return a tree entry of the rules directory."""
    return {"name": name, "object": {"text": text}}


@pytest.fixture
def install_graphql(monkeypatch: pytest.MonkeyPatch) -> InstallGraphql:
    """Return a factory installing a canned response for the GraphQL query."""

    def install(payload: dict[str, Any]) -> None:
        def graphql(query: str, token: str) -> dict[str, Any]:
            assert token == _TOKEN
            return payload

        monkeypatch.setattr(rules.github_api, "graphql", graphql)

    return install


def test_fetch_docs_reads_the_tiers_and_the_rule_pages(
    install_graphql: InstallGraphql,
) -> None:
    """Every tier and every markdown page of the rules directory is collected."""
    install_graphql(
        _graphql_payload(
            {
                "bronze": ["config-flow"],
                "silver": ["test-coverage"],
                "gold": ["devices"],
                "platinum": ["strict-typing"],
            },
            [_entry("config-flow.md", '---\ntitle: "Config flow"\n---\n')],
        )
    )

    docs = rules.fetch_docs(_TOKEN)

    assert docs.tiers == {
        "bronze": ["config-flow"],
        "silver": ["test-coverage"],
        "gold": ["devices"],
        "platinum": ["strict-typing"],
    }
    assert docs.rules == [
        RuleDoc(filename="config-flow.md", text='---\ntitle: "Config flow"\n---\n')
    ]


def test_fetch_docs_accepts_a_tier_entry_that_is_an_object(
    install_graphql: InstallGraphql,
) -> None:
    """A tier entry may name the rule directly or carry it in an `id` field."""
    install_graphql(
        _graphql_payload(
            {
                "bronze": [{"id": "config-flow", "note": "ignored"}],
                "silver": [],
                "gold": [],
                "platinum": [],
            },
            [],
        )
    )

    assert rules.fetch_docs(_TOKEN).tiers["bronze"] == ["config-flow"]


def test_fetch_docs_ignores_entries_that_are_not_markdown(
    install_graphql: InstallGraphql,
) -> None:
    """Non-markdown entries of the rules directory are not rule pages."""
    install_graphql(
        _graphql_payload(
            {"bronze": [], "silver": [], "gold": [], "platinum": []},
            [_entry("config-flow.md", ""), _entry("_category_.json", "{}")],
        )
    )

    assert [doc.filename for doc in rules.fetch_docs(_TOKEN).rules] == [
        "config-flow.md"
    ]


def test_build_index_renders_one_line_per_rule_under_a_header() -> None:
    """The index lists every rule of every tier with its title."""
    docs = rules.QualityScaleDocs(
        tiers={
            "bronze": ["config-flow"],
            "silver": ["test-coverage"],
            "gold": ["devices"],
            "platinum": ["strict-typing"],
        },
        rules=[
            RuleDoc("config-flow.md", '---\ntitle: "Config flow"\n---\n'),
            RuleDoc("test-coverage.md", '---\ntitle: "Above 95% test coverage"\n---\n'),
            RuleDoc("devices.md", '---\ntitle: "Devices"\n---\n'),
            RuleDoc("strict-typing.md", '---\ntitle: "Strict typing"\n---\n'),
        ],
    )

    assert rules.build_index(docs) == (
        "# Integration Quality Scale rules: tier | rule | title\n"
        "bronze | config-flow | Config flow\n"
        "silver | test-coverage | Above 95% test coverage\n"
        "gold | devices | Devices\n"
        "platinum | strict-typing | Strict typing\n"
    )


def test_build_index_leaves_the_title_empty_when_the_rule_has_no_page() -> None:
    """A rule listed in a tier without a documentation page still gets a line."""
    docs = rules.QualityScaleDocs(
        tiers={"bronze": ["config-flow"], "silver": [], "gold": [], "platinum": []},
        rules=[],
    )

    assert rules.build_index(docs).splitlines()[1] == "bronze | config-flow | "
