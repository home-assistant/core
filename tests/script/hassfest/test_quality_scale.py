"""Tests for hassfest quality scale validation."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from hassfest.model import Config, Integration
import pytest
import yaml

from script.hassfest import quality_scale

DOMAIN = "test_quality_scale"

type ValidateQualityScale = Callable[..., list[str]]


@pytest.fixture
def validate_quality_scale(
    config: Config, tmp_path: Path, mock_core_integration: None
) -> ValidateQualityScale:
    """Return a function that validates a quality scale file.

    By default the integration is Bronze, and every rule is exempt. Pass rules
    to override, and manifest keys to change the manifest.
    """

    def _validate(rules: dict[str, Any] | None = None, **manifest: Any) -> list[str]:
        path = tmp_path / DOMAIN
        path.mkdir()
        (path / "quality_scale.yaml").write_text(
            yaml.safe_dump(
                {
                    "rules": {
                        rule.name: {"status": "exempt", "comment": "Not applicable."}
                        for rule in quality_scale.ALL_RULES
                    }
                    | (rules or {})
                }
            )
        )
        integration = Integration(
            path,
            _config=config,
            _manifest={
                "domain": DOMAIN,
                "name": "Test",
                "quality_scale": "bronze",
                **manifest,
            },
        )

        quality_scale.validate({DOMAIN: integration}, config)

        return [error.error for error in integration.errors]

    return _validate


def _pull_request_error(reference: str) -> str:
    """Return the error for a comment on the brands rule with a reference."""
    return (
        f"[brands] The comment refers to a pull request ({reference})."
        " Describe what is missing or why the rule is exempt instead, and"
        " update the status in the pull request that completes the rule."
    )


@pytest.mark.parametrize(
    ("comment", "errors"),
    [
        pytest.param(
            "See https://github.com/home-assistant/core/pull/134027",
            [_pull_request_error("github.com/home-assistant/core/pull/134027")],
            id="pull_request_url",
        ),
        pytest.param(
            "The icon is in home-assistant/brands#11237.",
            [_pull_request_error("home-assistant/brands#11237")],
            id="repository_reference",
        ),
        pytest.param(
            "Will be fixed in PR #147064.",
            [_pull_request_error("PR #147064")],
            id="pr_with_hash",
        ),
        pytest.param(
            "Future enhancements. PR 153958",
            [_pull_request_error("PR 153958")],
            id="pr_without_hash",
        ),
        pytest.param(
            "Will be fixed in #12345.",
            [_pull_request_error("#12345")],
            id="bare_number",
        ),
        pytest.param(
            "Reauthentication will be added in a follow-up PR.",
            [],
            id="follow_up_without_number",
        ),
        pytest.param(
            "Blocked by https://github.com/home-assistant/core/issues/123456",
            [],
            id="issue_url",
        ),
        pytest.param("The device supports Wi-Fi 802.11#5.", [], id="hash_in_word"),
        pytest.param("The light reports the color #fff when off.", [], id="color"),
    ],
)
def test_pull_request_reference_in_comment(
    validate_quality_scale: ValidateQualityScale, comment: str, errors: list[str]
) -> None:
    """Test comments that refer to a pull request are rejected."""
    assert (
        validate_quality_scale({"brands": {"status": "exempt", "comment": comment}})
        == errors
    )
