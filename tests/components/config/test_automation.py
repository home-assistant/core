"""Test Automation config panel."""

from http import HTTPStatus
import json
from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import config
from homeassistant.components.automation import (
    async_get_blueprints,
    config as automation_validation,
)
from homeassistant.components.config import DOMAIN, automation
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import yaml as yaml_util

from .common import (
    BlockKind,
    assert_block_schema_errors_match,
    assert_error_paths_resolve,
)

_BLOCK_KINDS: dict[str, BlockKind] = {
    "triggers": "triggers",
    "conditions": "conditions",
    "actions": "actions",
}


@pytest.fixture
async def setup_automation(
    hass: HomeAssistant,
    automation_config: dict[str, Any],
) -> None:
    """Set up automation integration."""
    assert await async_setup_component(
        hass, "automation", {"automation": automation_config}
    )


@pytest.mark.parametrize("automation_config", [{}])
@pytest.mark.usefixtures("setup_automation")
async def test_get_automation_config(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_config_store: dict[str, Any],
) -> None:
    """Test getting automation config."""
    with patch.object(config, "SECTIONS", [automation]):
        await async_setup_component(hass, DOMAIN, {})

    client = await hass_client()

    hass_config_store["automations.yaml"] = [{"id": "sun"}, {"id": "moon"}]

    resp = await client.get("/api/config/automation/config/moon")

    assert resp.status == HTTPStatus.OK
    result = await resp.json()

    assert result == {"id": "moon"}


@pytest.mark.parametrize("automation_config", [{}])
@pytest.mark.usefixtures("setup_automation")
async def test_update_automation_config(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_config_store: dict[str, Any],
) -> None:
    """Test updating automation config."""
    with patch.object(config, "SECTIONS", [automation]):
        await async_setup_component(hass, DOMAIN, {})

    assert sorted(hass.states.async_entity_ids("automation")) == []

    client = await hass_client()

    orig_data = [{"id": "sun"}, {"id": "moon"}]
    hass_config_store["automations.yaml"] = orig_data

    resp = await client.post(
        "/api/config/automation/config/moon",
        data=json.dumps({"triggers": [], "actions": [], "conditions": []}),
    )
    await hass.async_block_till_done()
    assert sorted(hass.states.async_entity_ids("automation")) == [
        "automation.automation_1",
    ]
    assert hass.states.get("automation.automation_1").state == STATE_ON

    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"result": "ok"}

    new_data = hass_config_store["automations.yaml"]
    assert list(new_data[1]) == ["id", "triggers", "conditions", "actions"]
    assert new_data[1] == {
        "id": "moon",
        "triggers": [],
        "conditions": [],
        "actions": [],
    }


_EVENT_TRIGGER = {"trigger": "event", "event_type": "test_event"}
_UNKNOWN_ENTITY_CONDITION = {
    "condition": "state",
    # The UUID will fail being resolved to an entity_id
    "entity_id": "abcdabcdabcdabcdabcdabcdabcdabcd",
    "state": "blah",
}
_BLUEPRINT_INPUT = {
    "trigger_event": "test_event",
    "service_to_call": "test.automation",
    "a_number": 5,
}

_INVALID_CONFIGS = [
    pytest.param({"action": []}, id="missing_key"),
    pytest.param(
        {"trigger": {"trigger": "automation"}, "action": []},
        id="singular_key_single_trigger",
    ),
    pytest.param(
        {
            "trigger": _EVENT_TRIGGER,
            "condition": _UNKNOWN_ENTITY_CONDITION,
            "action": [],
        },
        id="singular_key_single_condition",
    ),
    pytest.param(
        {"trigger": _EVENT_TRIGGER, "action": _UNKNOWN_ENTITY_CONDITION},
        id="singular_key_single_action",
    ),
    pytest.param(
        {
            "triggers": [_EVENT_TRIGGER],
            "actions": [{"delay": "abc"}, {"delay": 1, "bogus": 2}],
            "mode": "bogus",
        },
        id="schema_errors",
    ),
    pytest.param(
        {
            "triggers": [
                _EVENT_TRIGGER,
                {"trigger": "state"},
                {"trigger": "automation"},
            ],
            "conditions": [_UNKNOWN_ENTITY_CONDITION],
            "actions": [_UNKNOWN_ENTITY_CONDITION],
        },
        id="platform_errors",
    ),
    pytest.param(
        {
            "triggers": [_EVENT_TRIGGER],
            "conditions": [{"or": [_UNKNOWN_ENTITY_CONDITION]}],
            "actions": [
                {
                    "if": [_UNKNOWN_ENTITY_CONDITION],
                    "then": [{"wait_for_trigger": [{"trigger": "state"}]}],
                    "else": {
                        "choose": [
                            {
                                "conditions": _UNKNOWN_ENTITY_CONDITION,
                                "sequence": [{"delay": "abc"}],
                            }
                        ]
                    },
                }
            ],
        },
        id="nested_blocks",
    ),
    pytest.param(
        {
            "trigger": [{"trigger": "event"}],
            "condition": {"condition": "state", "entity_id": "light.kitchen"},
            "action": [{"delay": "abc"}],
        },
        id="singular_keys_schema_errors",
    ),
    pytest.param(
        {
            "trigger": {"trigger": "state"},
            "condition": [_UNKNOWN_ENTITY_CONDITION],
            "action": [{"delay": 1}, _UNKNOWN_ENTITY_CONDITION],
        },
        id="singular_keys_platform_errors",
    ),
    pytest.param(
        {
            "triggers": [{"trigger": "event"}, {"trigger": "state"}],
            "actions": [
                {"delay": "abc"},
                _UNKNOWN_ENTITY_CONDITION,
                {"wait_for_trigger": [{"trigger": "automation"}]},
            ],
        },
        id="schema_and_platform_errors",
    ),
    pytest.param(
        {
            "triggers": [{"trigger": "state"}],
            "conditions": [_UNKNOWN_ENTITY_CONDITION],
            "actions": [{"delay": "abc"}],
        },
        id="schema_error_and_platform_errors_in_other_sections",
    ),
    pytest.param(
        {
            "trigger": {"trigger": "state"},
            "action": [],
            "mode": "bogus",
        },
        id="schema_error_at_root_and_platform_error_singular_key",
    ),
    pytest.param(
        {"actions": [_UNKNOWN_ENTITY_CONDITION]},
        id="missing_key_and_platform_error",
    ),
    pytest.param(
        {
            "triggers": [_EVENT_TRIGGER, 5],
            "conditions": [{"condition": "state", "entity_id": "light.kitchen"}],
            "actions": [{"delay": "abc"}],
        },
        id="schema_errors_in_all_sections",
    ),
    pytest.param(
        {
            "trigger": _EVENT_TRIGGER,
            "triggers": [{"trigger": "state"}],
            "actions": [],
        },
        id="singular_and_plural_trigger_keys",
    ),
    pytest.param(
        {
            "triggers": [_EVENT_TRIGGER],
            "condition": {"condition": "state", "entity_id": "light.kitchen"},
            "conditions": [_UNKNOWN_ENTITY_CONDITION],
            "actions": [],
        },
        id="singular_and_plural_condition_keys",
    ),
    pytest.param(
        {
            "triggers": [_EVENT_TRIGGER],
            "action": [],
            "actions": [_UNKNOWN_ENTITY_CONDITION],
        },
        id="singular_and_plural_action_keys",
    ),
    pytest.param(
        {
            "trigger": {"trigger": "state"},
            "action": [],
            "actions": [_UNKNOWN_ENTITY_CONDITION],
        },
        id="singular_trigger_key_and_singular_and_plural_action_keys",
    ),
    pytest.param(
        {
            "trigger": _EVENT_TRIGGER,
            "triggers": [{"trigger": "state"}],
            "condition": [_UNKNOWN_ENTITY_CONDITION],
            "action": [{"delay": "abc"}],
        },
        id="singular_and_plural_trigger_keys_and_singular_blocks",
    ),
]
_INVALID_BLUEPRINT_CONFIGS = [
    pytest.param(
        {
            "use_blueprint": {
                "path": "test_event_service.yaml",
                "input": _BLUEPRINT_INPUT | {"service_to_call": 5},
            },
        },
        id="blueprint_generated_config_error",
    ),
    pytest.param(
        {
            "alias": "Blueprint automation",
            "mode": "bogus",
            "use_blueprint": {
                "path": "test_event_service.yaml",
                "input": _BLUEPRINT_INPUT,
            },
        },
        id="blueprint_instance_key_error",
    ),
    pytest.param(
        {
            "mode": "bogus",
            "use_blueprint": {
                "path": "test_event_service.yaml",
                "input": _BLUEPRINT_INPUT | {"service_to_call": 5},
            },
        },
        id="blueprint_instance_key_and_generated_config_errors",
    ),
]


@pytest.mark.parametrize("automation_config", [{}])
@pytest.mark.parametrize(
    "updated_config",
    [
        *_INVALID_CONFIGS,
        *_INVALID_BLUEPRINT_CONFIGS,
        pytest.param(
            {"use_blueprint": {"path": "test_event_service.yaml", "input": {}}},
            id="blueprint_missing_input",
        ),
        pytest.param(
            {"use_blueprint": {"path": "not_found.yaml", "input": {}}},
            id="blueprint_not_found",
        ),
    ],
)
@pytest.mark.usefixtures("setup_automation")
async def test_update_automation_config_with_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_config_store: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
    snapshot: SnapshotAssertion,
    updated_config: dict[str, Any],
) -> None:
    """Test updating automation config with errors."""
    with patch.object(config, "SECTIONS", [automation]):
        await async_setup_component(hass, DOMAIN, {})

    assert sorted(hass.states.async_entity_ids("automation")) == []

    client = await hass_client()

    orig_data = [{"id": "sun"}, {"id": "moon"}]
    hass_config_store["automations.yaml"] = orig_data

    resp = await client.post(
        "/api/config/automation/config/moon",
        data=json.dumps(updated_config),
    )
    await hass.async_block_till_done()
    assert sorted(hass.states.async_entity_ids("automation")) == []

    assert resp.status == HTTPStatus.BAD_REQUEST
    result = await resp.json()
    assert result == snapshot
    assert_error_paths_resolve(updated_config, result["errors"])
    assert hass_config_store["automations.yaml"] == [{"id": "sun"}, {"id": "moon"}]
    # Assert the validation error is not logged
    assert result["message"].removeprefix("Message malformed: ") not in caplog.text


@pytest.mark.parametrize("config", _INVALID_CONFIGS)
def test_block_schema_errors_match_automation_schema(config: dict[str, Any]) -> None:
    """Test the schema of a block gives the errors the automation schema gives for it.

    The errors of a block are reported once because they are the same.
    """
    assert_block_schema_errors_match(
        automation_validation.PLATFORM_SCHEMA, _BLOCK_KINDS, config
    )


@pytest.mark.parametrize("config", _INVALID_BLUEPRINT_CONFIGS)
async def test_block_schema_errors_match_automation_schema_blueprint(
    hass: HomeAssistant, config: dict[str, Any]
) -> None:
    """Test the same for the config which is generated from a blueprint."""
    blueprint_inputs = await async_get_blueprints(hass).async_inputs_from_config(config)

    assert_block_schema_errors_match(
        automation_validation.PLATFORM_SCHEMA,
        _BLOCK_KINDS,
        blueprint_inputs.async_substitute(),
    )


@pytest.mark.parametrize("automation_config", [{}])
@pytest.mark.parametrize(
    ("updated_config", "validation_error"),
    [
        (
            {
                "use_blueprint": {
                    "path": "test_event_service.yaml",
                    "input": {
                        "trigger_event": "test_event",
                        "service_to_call": "test.automation",
                        "a_number": 5,
                    },
                },
            },
            "No substitution found for input blah",
        ),
    ],
)
@pytest.mark.usefixtures("setup_automation")
async def test_update_automation_config_with_blueprint_substitution_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_config_store: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
    updated_config: Any,
    validation_error: str,
) -> None:
    """Test updating automation config with errors."""
    with patch.object(config, "SECTIONS", [automation]):
        await async_setup_component(hass, DOMAIN, {})

    assert sorted(hass.states.async_entity_ids("automation")) == []

    client = await hass_client()

    orig_data = [{"id": "sun"}, {"id": "moon"}]
    hass_config_store["automations.yaml"] = orig_data

    with patch(
        "homeassistant.components.blueprint.models.BlueprintInputs.async_substitute",
        side_effect=yaml_util.UndefinedSubstitution("blah"),
    ):
        resp = await client.post(
            "/api/config/automation/config/moon",
            data=json.dumps(updated_config),
        )
        await hass.async_block_till_done()
    assert sorted(hass.states.async_entity_ids("automation")) == []

    assert resp.status != HTTPStatus.OK
    result = await resp.json()
    assert result == {
        "message": f"Message malformed: {validation_error}",
        "errors": [
            {
                "message": validation_error,
                "path": [],
                "code": None,
                "translation_key": None,
                "translation_domain": None,
                "translation_placeholders": {},
            }
        ],
    }
    # Assert the validation error is not logged
    assert validation_error not in caplog.text


@pytest.mark.parametrize("automation_config", [{}])
@pytest.mark.usefixtures("setup_automation")
async def test_update_automation_config_error_not_found_again(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_config_store: dict[str, Any],
) -> None:
    """Test the error is kept if validating again does not give any error."""
    with patch.object(config, "SECTIONS", [automation]):
        await async_setup_component(hass, DOMAIN, {})

    client = await hass_client()

    hass_config_store["automations.yaml"] = [{"id": "sun"}, {"id": "moon"}]

    with patch(
        "homeassistant.components.automation.config._async_collect_errors",
        return_value=[],
    ):
        resp = await client.post(
            "/api/config/automation/config/moon",
            data=json.dumps({"trigger": {"trigger": "automation"}, "action": []}),
        )

    assert resp.status == HTTPStatus.BAD_REQUEST
    # The path is the one in the validated config, except for a renamed key
    assert await resp.json() == {
        "message": (
            "Message malformed: Integration 'automation' does not provide trigger support at 'trigger[0]'"
        ),
        "errors": [
            {
                "message": "Integration 'automation' does not provide trigger support",
                "path": ["trigger", 0],
                "code": None,
                "translation_key": None,
                "translation_domain": None,
                "translation_placeholders": {},
            }
        ],
    }


@pytest.mark.parametrize("automation_config", [{}])
@pytest.mark.usefixtures("setup_automation")
async def test_update_remove_key_automation_config(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_config_store: dict[str, Any],
) -> None:
    """Test updating automation config while removing a key."""
    with patch.object(config, "SECTIONS", [automation]):
        await async_setup_component(hass, DOMAIN, {})

    assert sorted(hass.states.async_entity_ids("automation")) == []

    client = await hass_client()

    orig_data = [{"id": "sun", "key": "value"}, {"id": "moon", "key": "value"}]
    hass_config_store["automations.yaml"] = orig_data

    resp = await client.post(
        "/api/config/automation/config/moon",
        data=json.dumps({"triggers": [], "actions": [], "conditions": []}),
    )
    await hass.async_block_till_done()
    assert sorted(hass.states.async_entity_ids("automation")) == [
        "automation.automation_1",
    ]
    assert hass.states.get("automation.automation_1").state == STATE_ON

    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"result": "ok"}

    new_data = hass_config_store["automations.yaml"]
    assert list(new_data[1]) == ["id", "triggers", "conditions", "actions"]
    assert new_data[1] == {
        "id": "moon",
        "triggers": [],
        "conditions": [],
        "actions": [],
    }


@pytest.mark.parametrize("automation_config", [{}])
@pytest.mark.usefixtures("setup_automation")
async def test_bad_formatted_automations(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_config_store: dict[str, Any],
) -> None:
    """Test that we handle automations without ID."""
    with patch.object(config, "SECTIONS", [automation]):
        await async_setup_component(hass, DOMAIN, {})

    assert sorted(hass.states.async_entity_ids("automation")) == []

    client = await hass_client()

    orig_data = [
        {
            # No ID
            "action": {"event": "hello"}
        },
        {"id": "moon"},
    ]
    hass_config_store["automations.yaml"] = orig_data

    resp = await client.post(
        "/api/config/automation/config/moon",
        data=json.dumps({"triggers": [], "actions": [], "conditions": []}),
    )
    await hass.async_block_till_done()
    assert sorted(hass.states.async_entity_ids("automation")) == [
        "automation.automation_1",
    ]
    assert hass.states.get("automation.automation_1").state == STATE_ON

    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"result": "ok"}

    # Verify ID added
    new_data = hass_config_store["automations.yaml"]
    assert "id" in new_data[0]
    assert new_data[1] == {
        "id": "moon",
        "triggers": [],
        "conditions": [],
        "actions": [],
    }


@pytest.mark.parametrize(
    "automation_config",
    [
        [
            {
                "id": "sun",
                "trigger": {"trigger": "event", "event_type": "test_event"},
                "action": {"service": "test.automation"},
            },
            {
                "id": "moon",
                "trigger": {"trigger": "event", "event_type": "test_event"},
                "action": {"service": "test.automation"},
            },
        ],
    ],
)
@pytest.mark.usefixtures("setup_automation")
async def test_delete_automation(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
    hass_config_store: dict[str, Any],
) -> None:
    """Test deleting an automation."""

    assert len(entity_registry.entities) == 2

    with patch.object(config, "SECTIONS", [automation]):
        assert await async_setup_component(hass, DOMAIN, {})

    assert sorted(hass.states.async_entity_ids("automation")) == [
        "automation.automation_0",
        "automation.automation_1",
    ]

    client = await hass_client()

    orig_data = [{"id": "sun"}, {"id": "moon"}]
    hass_config_store["automations.yaml"] = orig_data

    resp = await client.delete("/api/config/automation/config/sun")
    await hass.async_block_till_done()

    assert sorted(hass.states.async_entity_ids("automation")) == [
        "automation.automation_1",
    ]

    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"result": "ok"}

    assert hass_config_store["automations.yaml"] == [{"id": "moon"}]

    assert len(entity_registry.entities) == 1


@pytest.mark.parametrize("automation_config", [{}])
@pytest.mark.usefixtures("setup_automation")
async def test_api_calls_require_admin(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_read_only_access_token: str,
    hass_config_store: dict[str, Any],
) -> None:
    """Test cloud APIs endpoints do not work as a normal user."""
    with patch.object(config, "SECTIONS", [automation]):
        await async_setup_component(hass, DOMAIN, {})

    hass_config_store["automations.yaml"] = [{"id": "sun"}, {"id": "moon"}]

    client = await hass_client(hass_read_only_access_token)

    # Get
    resp = await client.get("/api/config/automation/config/moon")
    assert resp.status == HTTPStatus.UNAUTHORIZED

    # Update
    resp = await client.post(
        "/api/config/automation/config/moon",
        data=json.dumps({"trigger": [], "action": [], "condition": []}),
    )
    assert resp.status == HTTPStatus.UNAUTHORIZED

    # Delete
    resp = await client.delete("/api/config/automation/config/sun")
    assert resp.status == HTTPStatus.UNAUTHORIZED
