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
    to override, config_flow_code to add a config_flow.py, and manifest keys to
    change the manifest.
    """

    def _validate(
        rules: dict[str, Any] | None = None,
        *,
        config_flow_code: str | None = None,
        **manifest: Any,
    ) -> list[str]:
        path = tmp_path / DOMAIN
        path.mkdir()
        if config_flow_code is not None:
            (path / "config_flow.py").write_text(config_flow_code)
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


@pytest.mark.parametrize(
    ("rule", "config_flow_code"),
    [
        pytest.param(
            "unique-config-entry",
            "def step(self):\n    self._async_abort_entries_match({})\n",
            id="unique_config_entry_abort_entries_match",
        ),
        pytest.param(
            "unique-config-entry",
            "async def step(self):\n"
            "    await self.async_set_unique_id('id')\n"
            "    self._abort_if_unique_id_configured()\n",
            id="unique_config_entry_unique_id",
        ),
        pytest.param(
            "unique-config-entry",
            "class Flow(InfraredConsumerConfigFlow, domain='test'):\n    pass\n",
            id="unique_config_entry_infrared_consumer_flow",
        ),
        pytest.param(
            "unique-config-entry",
            "class Flow(InfraredConsumerReconfigureConfigFlow, domain='test'):\n"
            "    pass\n",
            id="unique_config_entry_infrared_consumer_reconfigure_flow",
        ),
        pytest.param(
            "unique-config-entry",
            "class Flow(infrared.InfraredConsumerConfigFlow, domain='test'):\n"
            "    pass\n",
            id="unique_config_entry_infrared_consumer_flow_module",
        ),
        pytest.param(
            "unique-config-entry",
            "class Flow(InfraredConsumerConfigFlow, domain='test'):\n"
            "    async def async_step_user(self, user_input=None):\n"
            "        self._async_abort_infrared_entities_match(user_input)\n",
            id="unique_config_entry_infrared_consumer_own_user_step",
        ),
        pytest.param(
            "reconfiguration-flow",
            "class Flow(ConfigFlow, domain='test'):\n"
            "    async def async_step_reconfigure(self, user_input=None):\n"
            "        pass\n",
            id="reconfiguration_flow_async_step_reconfigure",
        ),
        pytest.param(
            "reconfiguration-flow",
            "class Flow(InfraredConsumerReconfigureConfigFlow, domain='test'):\n"
            "    pass\n",
            id="reconfiguration_flow_infrared_consumer_reconfigure_flow",
        ),
        pytest.param(
            "reconfiguration-flow",
            "class Flow(infrared.InfraredConsumerReconfigureConfigFlow, domain='test'):\n"
            "    pass\n",
            id="reconfiguration_flow_infrared_consumer_reconfigure_flow_module",
        ),
    ],
)
def test_config_flow_rule_done(
    validate_quality_scale: ValidateQualityScale, rule: str, config_flow_code: str
) -> None:
    """Test config flows that follow a done rule pass."""
    assert (
        validate_quality_scale({rule: "done"}, config_flow_code=config_flow_code) == []
    )


@pytest.mark.parametrize(
    ("rule", "config_flow_code", "error"),
    [
        pytest.param(
            "unique-config-entry",
            "def step(self):\n    self.async_create_entry()\n",
            "Integration doesn't prevent the same device or service from being"
            " set up twice in {config_flow_file}",
            id="unique_config_entry_no_check",
        ),
        pytest.param(
            "unique-config-entry",
            "class Flow(InfraredConsumerConfigFlow, domain='test'):\n"
            "    async def async_step_user(self, user_input=None):\n"
            "        return self.async_create_entry()\n",
            "Integration doesn't prevent the same device or service from being"
            " set up twice in {config_flow_file}",
            id="unique_config_entry_infrared_consumer_own_user_step_no_check",
        ),
        pytest.param(
            "reconfiguration-flow",
            "class Flow(ConfigFlow, domain='test'):\n    pass\n",
            "Integration does not support a reconfiguration flow"
            " (is missing `async_step_reconfigure` in {config_flow_file})",
            id="reconfiguration_flow_config_flow",
        ),
        pytest.param(
            "reconfiguration-flow",
            "class Flow(InfraredConsumerConfigFlow, domain='test'):\n    pass\n",
            "Integration does not support a reconfiguration flow"
            " (is missing `async_step_reconfigure` in {config_flow_file})",
            id="reconfiguration_flow_infrared_consumer_flow",
        ),
    ],
)
def test_config_flow_rule_done_not_met(
    validate_quality_scale: ValidateQualityScale,
    tmp_path: Path,
    rule: str,
    config_flow_code: str,
    error: str,
) -> None:
    """Test config flows that do not follow a done rule fail."""
    config_flow_file = tmp_path / DOMAIN / "config_flow.py"

    assert validate_quality_scale(
        {rule: "done"}, config_flow_code=config_flow_code
    ) == [
        f"[{rule}] {error.format(config_flow_file=config_flow_file)}",
        quality_scale.RULE_URL.format(rule_name=rule),
    ]
