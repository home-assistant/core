"""Test Automation config panel."""

from http import HTTPStatus
import json
from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components import config
from homeassistant.components.config import DOMAIN, automation
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import yaml as yaml_util


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


@pytest.mark.parametrize("automation_config", [{}])
@pytest.mark.parametrize(
    ("updated_config", "validation_error", "errors"),
    [
        (
            {"action": []},
            "required key not provided at 'triggers'",
            [
                {
                    "message": "required key not provided",
                    "path": ["triggers"],
                    "code": "required",
                }
            ],
        ),
        (
            {
                "trigger": {"trigger": "automation"},
                "action": [],
            },
            "Integration 'automation' does not provide trigger support "
            "at 'triggers[0]'",
            [
                {
                    "message": "Integration 'automation' does not provide trigger support",
                    "path": ["triggers", 0],
                    "code": None,
                }
            ],
        ),
        (
            {
                "triggers": [
                    {"trigger": "event", "event_type": "test_event"},
                    {"trigger": "state", "entity_id": "light.kitchen", "for": "abc"},
                ],
                "actions": [],
            },
            "offset abc should be format 'HH:MM', 'HH:MM:SS' or 'HH:MM:SS.F' "
            "at 'triggers[1].for'",
            [
                {
                    "message": "offset abc should be format 'HH:MM', 'HH:MM:SS' "
                    "or 'HH:MM:SS.F'",
                    "path": ["triggers", 1, "for"],
                    "code": None,
                }
            ],
        ),
        (
            {
                "triggers": [{"trigger": "event", "event_type": "test_event"}],
                "actions": [
                    {"delay": 1},
                    {
                        "device_id": "a51a57e5af051eb403d56eb9e6fd691c",
                        "domain": "light",
                        "type": "turn_on",
                        "entity_id": "7d18a157b7c00adbf2982ea7de0d0362",
                    },
                ],
            },
            "Unknown device 'a51a57e5af051eb403d56eb9e6fd691c'",
            [
                {
                    "message": "Unknown device 'a51a57e5af051eb403d56eb9e6fd691c'",
                    "path": ["actions", 1],
                    "code": None,
                }
            ],
        ),
        (
            {
                "triggers": [{"trigger": "event", "event_type": "test_event"}],
                "actions": [{"delay": "abc"}, {"non_existing": "test.automation"}],
                "mode": "non_existing",
            },
            "offset abc should be format 'HH:MM', 'HH:MM:SS' or 'HH:MM:SS.F' "
            "at 'actions[0].delay'",
            [
                {
                    "message": "offset abc should be format 'HH:MM', 'HH:MM:SS' "
                    "or 'HH:MM:SS.F'",
                    "path": ["actions", 0, "delay"],
                    "code": None,
                },
                {
                    "message": "Unable to determine action",
                    "path": ["actions", 1],
                    "code": None,
                },
                {
                    "message": "value must be one of "
                    "['parallel', 'queued', 'restart', 'single']",
                    "path": ["mode"],
                    "code": "not_in_list",
                },
            ],
        ),
        (
            {
                "triggers": [
                    {"trigger": "state", "entity_id": "light.kitchen", "for": "abc"},
                    {"trigger": "state", "entity_id": "light.kitchen", "for": "xyz"},
                ],
                "conditions": [{"condition": "non_existing"}],
                "actions": [
                    {
                        "if": [{"condition": "non_existing"}],
                        "then": [{"wait_for_trigger": [{"trigger": "non_existing"}]}],
                    },
                ],
            },
            "offset abc should be format 'HH:MM', 'HH:MM:SS' or 'HH:MM:SS.F' "
            "at 'triggers[0].for'",
            [
                {
                    "message": "offset abc should be format 'HH:MM', 'HH:MM:SS' "
                    "or 'HH:MM:SS.F'",
                    "path": ["triggers", 0, "for"],
                    "code": None,
                },
                {
                    "message": "offset xyz should be format 'HH:MM', 'HH:MM:SS' "
                    "or 'HH:MM:SS.F'",
                    "path": ["triggers", 1, "for"],
                    "code": None,
                },
                {
                    "message": 'Invalid condition "non_existing" specified',
                    "path": ["conditions", 0],
                    "code": None,
                },
                {
                    "message": 'Invalid condition "non_existing" specified',
                    "path": ["actions", 0, "if", 0],
                    "code": None,
                },
                {
                    "message": "Invalid trigger 'non_existing' specified",
                    "path": ["actions", 0, "then", 0, "wait_for_trigger", 0],
                    "code": None,
                },
            ],
        ),
        (
            {
                "triggers": [{"trigger": "event", "event_type": "test_event"}],
                "actions": [
                    {
                        "action": "light.turn_on",
                        "data": {"brightness_pct": "{{ 50 + "},
                    }
                ],
            },
            "invalid template (TemplateSyntaxError: unexpected 'end of template') "
            "at 'actions[0].data.brightness_pct'",
            [
                {
                    "message": "invalid template (TemplateSyntaxError: "
                    "unexpected 'end of template')",
                    "path": ["actions", 0, "data", "brightness_pct"],
                    "code": None,
                }
            ],
        ),
        (
            {
                "triggers": [{"trigger": "device", "device_id": "", "domain": ""}],
                "actions": [],
            },
            "required key not provided at 'triggers[0].device_id'",
            [
                {
                    "message": "required key not provided",
                    "path": ["triggers", 0, "device_id"],
                    "code": "required",
                }
            ],
        ),
        (
            {
                "triggers": [{"trigger": "event", "event_type": "test_event"}],
                "actions": [{"device_id": "abcd", "domain": ""}],
            },
            "required key not provided at 'actions[0].domain'",
            [
                {
                    "message": "required key not provided",
                    "path": ["actions", 0, "domain"],
                    "code": "required",
                }
            ],
        ),
        (
            {
                "triggers": [{"trigger": "device", "device_id": "", "domain": ""}],
                "conditions": [{"condition": "template", "value_template": "{{ "}],
                "actions": [{"delay": 1}, {"device_id": "abcd", "domain": ""}],
            },
            "invalid template (TemplateSyntaxError: unexpected 'end of template') "
            "at 'conditions[0].value_template'",
            [
                {
                    "message": "invalid template (TemplateSyntaxError: "
                    "unexpected 'end of template')",
                    "path": ["conditions", 0, "value_template"],
                    "code": None,
                },
                {
                    "message": "required key not provided",
                    "path": ["triggers", 0, "device_id"],
                    "code": "required",
                },
                {
                    "message": "required key not provided",
                    "path": ["actions", 1, "domain"],
                    "code": "required",
                },
            ],
        ),
        (
            {
                "trigger": {"trigger": "event", "event_type": "test_event"},
                "condition": {
                    "condition": "state",
                    # The UUID will fail being resolved to en entity_id
                    "entity_id": "abcdabcdabcdabcdabcdabcdabcdabcd",
                    "state": "blah",
                },
                "action": [],
            },
            "Unknown entity registry entry abcdabcdabcdabcdabcdabcdabcdabcd "
            "at 'conditions[0]'",
            [
                {
                    "message": "Unknown entity registry entry "
                    "abcdabcdabcdabcdabcdabcdabcdabcd",
                    "path": ["conditions", 0],
                    "code": None,
                }
            ],
        ),
        (
            {
                "trigger": {"trigger": "event", "event_type": "test_event"},
                "action": {
                    "condition": "state",
                    # The UUID will fail being resolved to en entity_id
                    "entity_id": "abcdabcdabcdabcdabcdabcdabcdabcd",
                    "state": "blah",
                },
            },
            "Unknown entity registry entry abcdabcdabcdabcdabcdabcdabcdabcd "
            "at 'actions[0]'",
            [
                {
                    "message": "Unknown entity registry entry "
                    "abcdabcdabcdabcdabcdabcdabcdabcd",
                    "path": ["actions", 0],
                    "code": None,
                }
            ],
        ),
        (
            {"trigger": [], "triggers": [None], "actions": []},
            "Cannot specify both 'trigger' and 'triggers'. Please use 'triggers' only.",
            [
                {
                    "message": "Cannot specify both 'trigger' and 'triggers'. "
                    "Please use 'triggers' only.",
                    "path": [],
                    "code": None,
                },
                {
                    "message": "expected a mapping",
                    "path": ["triggers", 0],
                    "code": "not_a_dictionary",
                },
            ],
        ),
        (
            {
                "use_blueprint": {"path": "test_event_service.yaml", "input": {}},
            },
            "Missing input a_number, service_to_call, trigger_event",
            [
                {
                    "message": "Missing input a_number, service_to_call, trigger_event",
                    "path": [],
                    "code": None,
                }
            ],
        ),
    ],
)
@pytest.mark.usefixtures("setup_automation")
async def test_update_automation_config_with_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_config_store: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
    updated_config: Any,
    validation_error: str,
    errors: list[dict[str, Any]],
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
    assert result == {
        "message": f"Message malformed: {validation_error}",
        "errors": errors,
    }
    # Assert the validation error is not logged
    assert validation_error not in caplog.text


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

    assert resp.status == HTTPStatus.BAD_REQUEST
    result = await resp.json()
    assert result == {
        "message": f"Message malformed: {validation_error}",
        "errors": [{"message": validation_error, "path": [], "code": None}],
    }
    # Assert the validation error is not logged
    assert validation_error not in caplog.text


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
