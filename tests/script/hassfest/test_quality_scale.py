"""Tests for hassfest quality scale validation."""

from pathlib import Path

from hassfest.model import Config, Integration
import pytest
import yaml

from script.hassfest import quality_scale

DOMAIN = "test_quality_scale"


def _validate(config: Config, tmp_path: Path, comment: str) -> list[str]:
    """Validate a Bronze integration with the given comment on the brands rule.

    The other rules are exempt with a plain comment. Return the quality scale
    errors.
    """
    path = tmp_path / DOMAIN
    path.mkdir()
    (path / "quality_scale.yaml").write_text(
        yaml.safe_dump(
            {
                "rules": {
                    rule.name: {"status": "exempt", "comment": "Not applicable."}
                    for rule in quality_scale.ALL_RULES
                }
                | {"brands": {"status": "exempt", "comment": comment}}
            }
        )
    )
    integration = Integration(
        path,
        _config=config,
        _manifest={"domain": DOMAIN, "name": "Test", "quality_scale": "bronze"},
    )

    quality_scale.validate({DOMAIN: integration}, config)

    return [error.error for error in integration.errors]


@pytest.mark.usefixtures("mock_core_integration")
@pytest.mark.parametrize(
    ("comment", "reference"),
    [
        (
            "See https://github.com/home-assistant/core/pull/134027",
            "github.com/home-assistant/core/pull/134027",
        ),
        (
            "The icon is in home-assistant/brands#11237.",
            "home-assistant/brands#11237",
        ),
        ("Will be fixed in PR #147064.", "PR #147064"),
        ("Future enhancements. PR 153958", "PR 153958"),
        ("Will be fixed in #12345.", "#12345"),
    ],
)
def test_pull_request_reference_in_comment(
    config: Config, tmp_path: Path, comment: str, reference: str
) -> None:
    """Test a comment that refers to a pull request is rejected."""
    assert _validate(config, tmp_path, comment) == [
        f"[brands] The comment refers to a pull request ({reference})."
        " Describe what is missing or why the rule is exempt instead, and"
        " update the status in the pull request that completes the rule."
    ]


@pytest.mark.usefixtures("mock_core_integration")
@pytest.mark.parametrize(
    "comment",
    [
        "Reauthentication will be added in a follow-up PR.",
        "Blocked by https://github.com/home-assistant/core/issues/123456",
        "The device supports Wi-Fi 802.11#5.",
        "The light reports the color #fff when off.",
    ],
)
def test_comment_without_pull_request_reference(
    config: Config, tmp_path: Path, comment: str
) -> None:
    """Test a comment without a pull request reference is accepted."""
    assert _validate(config, tmp_path, comment) == []
