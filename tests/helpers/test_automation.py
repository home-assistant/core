"""Test automation helpers."""

from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import Mock

import pytest
import voluptuous as vol

from homeassistant.const import CONF_CONDITION, CONF_PLATFORM
from homeassistant.core import (
    CALLBACK_TYPE,
    DOMAIN as HOMEASSISTANT_DOMAIN,
    HomeAssistant,
)
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.automation import (
    ValidationFinding,
    ValidationIssueReporter,
    async_call_platform_validator,
    async_clear_validation_issues,
    async_create_validation_issue,
    get_absolute_description_key,
    get_relative_description_key,
    move_options_fields_to_top_level,
    move_top_level_schema_fields_to_options,
)
from homeassistant.helpers.condition import Condition, async_validate_conditions_config
from homeassistant.helpers.script import async_validate_actions_config
from homeassistant.helpers.trigger import (
    Trigger,
    TriggerActionRunner,
    TriggerNotTriggeredReporter,
    async_validate_trigger_config,
)
from homeassistant.helpers.typing import ConfigType

from tests.common import MockModule, mock_integration, mock_platform


@pytest.mark.parametrize(
    ("relative_key", "absolute_key"),
    [
        ("turned_on", "homeassistant.turned_on"),
        ("_", "homeassistant"),
        ("_state", "state"),
    ],
)
def test_absolute_description_key(relative_key: str, absolute_key: str) -> None:
    """Test absolute description key."""
    DOMAIN = "homeassistant"
    assert get_absolute_description_key(DOMAIN, relative_key) == absolute_key


@pytest.mark.parametrize(
    ("relative_key", "absolute_key"),
    [
        ("turned_on", "homeassistant.turned_on"),
        ("_", "homeassistant"),
        ("_state", "state"),
    ],
)
def test_relative_description_key(relative_key: str, absolute_key: str) -> None:
    """Test relative description key."""
    DOMAIN = "homeassistant"
    assert get_relative_description_key(DOMAIN, absolute_key) == relative_key


@pytest.mark.parametrize(
    ("config", "schema_dict", "expected_config"),
    [
        (
            {
                "platform": "test",
                "entity": "sensor.test",
                "from": "open",
                "to": "closed",
                "for": {"hours": 1},
                "attribute": "state",
                "value_template": "{{ value_json.val }}",
                "extra_field": "extra_value",
            },
            {},
            {
                "platform": "test",
                "entity": "sensor.test",
                "from": "open",
                "to": "closed",
                "for": {"hours": 1},
                "attribute": "state",
                "value_template": "{{ value_json.val }}",
                "extra_field": "extra_value",
                "options": {},
            },
        ),
        (
            {
                "platform": "test",
                "entity": "sensor.test",
                "from": "open",
                "to": "closed",
                "for": {"hours": 1},
                "attribute": "state",
                "value_template": "{{ value_json.val }}",
                "extra_field": "extra_value",
            },
            {
                vol.Required("entity"): str,
                vol.Optional("from"): str,
                vol.Optional("to"): str,
                vol.Optional("for"): dict,
                vol.Optional("attribute"): str,
                vol.Optional("value_template"): str,
            },
            {
                "platform": "test",
                "extra_field": "extra_value",
                "options": {
                    "entity": "sensor.test",
                    "from": "open",
                    "to": "closed",
                    "for": {"hours": 1},
                    "attribute": "state",
                    "value_template": "{{ value_json.val }}",
                },
            },
        ),
    ],
)
async def test_move_schema_fields_to_options(
    config, schema_dict, expected_config
) -> None:
    """Test moving schema fields to options."""
    assert (
        move_top_level_schema_fields_to_options(config, schema_dict) == expected_config
    )


@pytest.mark.parametrize(
    ("config", "expected_config"),
    [
        (
            {
                "platform": "test",
                "options": {
                    "entity": "sensor.test",
                    "from": "open",
                    "to": "closed",
                    "for": {"hours": 1},
                },
            },
            {
                "platform": "test",
                "entity": "sensor.test",
                "from": "open",
                "to": "closed",
                "for": {"hours": 1},
            },
        ),
        (
            {
                "platform": "test",
                "entity": "sensor.test",
                "from": "open",
                "to": "closed",
                "for": {"hours": 1},
            },
            {
                "platform": "test",
                "entity": "sensor.test",
                "from": "open",
                "to": "closed",
                "for": {"hours": 1},
            },
        ),
        (
            {
                "platform": "test",
                "options": 456,
            },
            {
                "platform": "test",
                "options": 456,
            },
        ),
        (
            {
                "platform": "test",
                "options": {
                    "entity": "sensor.test",
                },
                "extra_field": "extra_value",
            },
            {
                "platform": "test",
                "options": {
                    "entity": "sensor.test",
                },
                "extra_field": "extra_value",
            },
        ),
    ],
)
async def test_move_options_fields_to_top_level(config, expected_config) -> None:
    """Test moving options fields to top-level."""
    base_schema = vol.Schema({vol.Required("platform"): str})
    original_config = config.copy()
    assert move_options_fields_to_top_level(config, base_schema) == expected_config
    assert config == original_config  # Ensure original config is not modified


# Findings reported by the mock validators below. The generic machinery does not
# interpret their contents, so any finding type/key is fine for these tests.
_TRIGGER_FINDING = ValidationFinding(
    finding_type="mock_trigger_finding",
    issue_key="trigger_key",
    placeholders={"detail": "trigger"},
)
_CONDITION_FINDING = ValidationFinding(
    finding_type="mock_condition_finding",
    issue_key="condition_key",
    placeholders={"detail": "condition"},
)


class _MockReportingTrigger(Trigger):
    """Trigger whose validator opts in to the reporter and reports a finding."""

    @classmethod
    async def async_validate_complete_config(
        cls,
        hass: HomeAssistant,
        complete_config: ConfigType,
        *,
        issue_reporter: ValidationIssueReporter | None = None,
    ) -> ConfigType:
        """Report a finding when a reporter is supplied, then validate normally."""
        if issue_reporter is not None:
            issue_reporter(_TRIGGER_FINDING)
        return await super().async_validate_complete_config(hass, complete_config)

    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return config

    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,
    ) -> CALLBACK_TYPE:
        """Attach the trigger."""
        return lambda: None


class _MockReportingCondition(Condition):
    """Condition whose validator opts in to the reporter and reports a finding."""

    @classmethod
    async def async_validate_complete_config(
        cls,
        hass: HomeAssistant,
        complete_config: ConfigType,
        *,
        issue_reporter: ValidationIssueReporter | None = None,
    ) -> ConfigType:
        """Report a finding when a reporter is supplied, then validate normally."""
        if issue_reporter is not None:
            issue_reporter(_CONDITION_FINDING)
        return await super().async_validate_complete_config(hass, complete_config)

    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate config."""
        return config

    def _async_check(self, **kwargs: Any) -> bool:
        """Check the condition."""
        return True


def _register_mock_trigger_platform(hass: HomeAssistant) -> None:
    """Register a trigger platform exposing the reporting mock trigger."""

    async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
        return {"_": _MockReportingTrigger}

    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.trigger", Mock(async_get_triggers=async_get_triggers))


def _register_mock_condition_platform(hass: HomeAssistant) -> None:
    """Register a condition platform exposing the reporting mock condition."""

    async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
        return {"_": _MockReportingCondition}

    mock_integration(hass, MockModule("test"))
    mock_platform(
        hass, "test.condition", Mock(async_get_conditions=async_get_conditions)
    )


async def test_trigger_validator_reports_finding(hass: HomeAssistant) -> None:
    """A trigger validator reaches the reporter via async_validate_trigger_config."""
    _register_mock_trigger_platform(hass)
    findings: list[ValidationFinding] = []
    validated = await async_validate_trigger_config(
        hass, [{CONF_PLATFORM: "test"}], issue_reporter=findings.append
    )
    assert validated == [{CONF_PLATFORM: "test"}]
    assert findings == [_TRIGGER_FINDING]


async def test_trigger_validator_no_reporter(hass: HomeAssistant) -> None:
    """Without a reporter the opted-in trigger validator still validates cleanly."""
    _register_mock_trigger_platform(hass)
    validated = await async_validate_trigger_config(hass, [{CONF_PLATFORM: "test"}])
    assert validated == [{CONF_PLATFORM: "test"}]


async def _validate_via_conditions(
    hass: HomeAssistant, reporter: ValidationIssueReporter
) -> None:
    """Reach the condition validator through the condition pipeline."""
    await async_validate_conditions_config(
        hass, [{CONF_CONDITION: "test"}], issue_reporter=reporter
    )


async def _validate_via_actions(
    hass: HomeAssistant, reporter: ValidationIssueReporter
) -> None:
    """Reach the condition validator through the action pipeline.

    A bare condition is a ``check_condition`` action, so the action pipeline
    forwards the reporter to the same condition validator.
    """
    await async_validate_actions_config(
        hass, [{CONF_CONDITION: "test"}], issue_reporter=reporter
    )


@pytest.mark.parametrize(
    "validate",
    [
        pytest.param(_validate_via_conditions, id="condition_pipeline"),
        pytest.param(_validate_via_actions, id="action_pipeline"),
    ],
)
async def test_condition_validator_reports_finding(
    hass: HomeAssistant,
    validate: Callable[[HomeAssistant, ValidationIssueReporter], Awaitable[None]],
) -> None:
    """A condition validator reaches the reporter through the condition and action paths."""
    _register_mock_condition_platform(hass)
    findings: list[ValidationFinding] = []
    await validate(hass, findings.append)
    assert findings == [_CONDITION_FINDING]


async def test_call_platform_validator_signature_inspection(
    hass: HomeAssistant,
) -> None:
    """The reporter is only forwarded to validators that declare the parameter."""
    calls: list[str] = []

    async def legacy_validator(hass: HomeAssistant, conf: ConfigType) -> ConfigType:
        # Two-arg legacy signature - must not receive issue_reporter.
        return conf

    async def opted_in_validator(
        hass: HomeAssistant,
        conf: ConfigType,
        *,
        issue_reporter: ValidationIssueReporter | None = None,
    ) -> ConfigType:
        if issue_reporter is not None:
            calls.append("reporter")
        return conf

    reporter = calls.append
    # Legacy validator: no TypeError, reporter not delivered.
    await async_call_platform_validator(legacy_validator, hass, {}, reporter)
    assert calls == []
    # Opted-in validator: reporter delivered.
    await async_call_platform_validator(opted_in_validator, hass, {}, reporter)
    assert calls == ["reporter"]


_SAMPLE_DEVICE_ID = "composite00000000000000000000ab"


def _sample_finding() -> ValidationFinding:
    """Build a representative validation finding."""
    return ValidationFinding(
        finding_type="event_trigger_composite_device_id",
        issue_key=_SAMPLE_DEVICE_ID,
        placeholders={
            "device_id": _SAMPLE_DEVICE_ID,
            "devices": "Split device 1 (abc)",
        },
    )


def test_create_and_clear_validation_issue_with_edit(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """A finding is filed under homeassistant, attributed to the owner via issue_domain."""
    issue_id = async_create_validation_issue(
        hass,
        _sample_finding(),
        issue_domain="automation",
        owner_key="1234",
        name="Test automation",
        entity_id="automation.test",
        edit_url="/config/automation/edit/1234",
    )
    assert (
        issue_id
        == f"automation_event_trigger_composite_device_id_1234_{_SAMPLE_DEVICE_ID}"
    )

    # Filed under the homeassistant domain (where the translations live), attributed to
    # the owning integration via issue_domain.
    issue = issue_registry.async_get_issue(HOMEASSISTANT_DOMAIN, issue_id)
    assert issue is not None
    assert issue.issue_domain == "automation"
    assert issue.is_fixable is False
    assert issue.severity == ir.IssueSeverity.ERROR
    assert issue.translation_key == "event_trigger_composite_device_id"
    assert issue.translation_placeholders["edit"] == "/config/automation/edit/1234"
    assert issue.translation_placeholders["device_id"] == _SAMPLE_DEVICE_ID
    assert issue.translation_placeholders["name"] == "Test automation"

    async_clear_validation_issues(hass, [issue_id])
    assert issue_registry.async_get_issue(HOMEASSISTANT_DOMAIN, issue_id) is None


def test_create_validation_issue_without_edit(
    hass: HomeAssistant, issue_registry: ir.IssueRegistry
) -> None:
    """The no-edit translation key is used for owners without a deep link."""
    issue_id = async_create_validation_issue(
        hass,
        _sample_finding(),
        issue_domain="template",
        owner_key="my_template",
        name="My template",
        entity_id="sensor.my_template",
        edit_url=None,
    )
    issue = issue_registry.async_get_issue(HOMEASSISTANT_DOMAIN, issue_id)
    assert issue is not None
    assert issue.issue_domain == "template"
    assert issue.translation_key == "event_trigger_composite_device_id_no_edit"
    assert "edit" not in issue.translation_placeholders
