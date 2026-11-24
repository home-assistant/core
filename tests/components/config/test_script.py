"""Tests for config/script."""

from http import HTTPStatus
import json
from typing import Any
from unittest.mock import patch

import probatio
import pytest
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import config
from homeassistant.components.config import DOMAIN, script
from homeassistant.components.script import (
    async_get_blueprints,
    config as script_validation,
)
from homeassistant.const import STATE_OFF, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.validation_errors import ValidationErrors
from homeassistant.setup import async_setup_component
from homeassistant.util import yaml as yaml_util

from .common import (
    BlockKind,
    assert_block_schema_errors_match,
    assert_error_paths_resolve,
)

_BLOCK_KINDS: dict[str, BlockKind] = {"sequence": "actions"}


@pytest.fixture(autouse=True)
async def setup_script(hass: HomeAssistant, script_config: dict[str, Any]) -> None:
    """Set up script integration."""
    assert await async_setup_component(hass, "script", {"script": script_config})


@pytest.mark.parametrize("script_config", [{}])
async def test_get_script_config(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_config_store: dict[str, Any],
) -> None:
    """Test getting script config."""
    with patch.object(config, "SECTIONS", [script]):
        await async_setup_component(hass, DOMAIN, {})

    client = await hass_client()

    hass_config_store["scripts.yaml"] = {
        "sun": {"alias": "Sun"},
        "moon": {"alias": "Moon"},
    }

    resp = await client.get("/api/config/script/config/moon")

    assert resp.status == HTTPStatus.OK
    result = await resp.json()

    assert result == {"alias": "Moon"}


@pytest.mark.parametrize("script_config", [{}])
async def test_update_script_config(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_config_store: dict[str, Any],
) -> None:
    """Test updating script config."""
    with patch.object(config, "SECTIONS", [script]):
        await async_setup_component(hass, DOMAIN, {})

    assert sorted(hass.states.async_entity_ids("script")) == []

    client = await hass_client()

    orig_data = {"sun": {"alias": "Sun"}, "moon": {"alias": "Moon"}}
    hass_config_store["scripts.yaml"] = orig_data

    resp = await client.post(
        "/api/config/script/config/moon",
        data=json.dumps({"alias": "Moon updated", "sequence": []}),
    )
    await hass.async_block_till_done()
    assert sorted(hass.states.async_entity_ids("script")) == [
        "script.moon",
        "script.sun",
    ]
    assert hass.states.get("script.moon").state == STATE_OFF
    assert hass.states.get("script.sun").state == STATE_UNAVAILABLE

    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"result": "ok"}

    new_data = hass_config_store["scripts.yaml"]
    assert list(new_data["moon"]) == ["alias", "sequence"]
    assert new_data["moon"] == {"alias": "Moon updated", "sequence": []}


@pytest.mark.parametrize("script_config", [{}])
@pytest.mark.parametrize(
    "updated_config",
    [
        pytest.param({"alias": "Turn on", "sequence": []}, id="script"),
        pytest.param(
            {
                "use_blueprint": {
                    "path": "test_service.yaml",
                    "input": {"service_to_call": "test.automation"},
                },
            },
            id="blueprint",
        ),
    ],
)
async def test_invalid_object_id(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_config_store: dict[str, Any],
    updated_config: dict[str, Any],
) -> None:
    """Test creating a script with an invalid object_id."""
    with patch.object(config, "SECTIONS", [script]):
        await async_setup_component(hass, DOMAIN, {})

    assert sorted(hass.states.async_entity_ids("script")) == []

    client = await hass_client()

    hass_config_store["scripts.yaml"] = {}

    resp = await client.post(
        "/api/config/script/config/turn_on",
        data=json.dumps(updated_config),
    )
    await hass.async_block_till_done()
    assert sorted(hass.states.async_entity_ids("script")) == []

    assert resp.status == HTTPStatus.BAD_REQUEST
    result = await resp.json()
    assert result == {
        "message": (
            "Message malformed: A script's object_id must not be one of "
            "reload, toggle, turn_off, turn_on"
        ),
        "errors": [
            {
                "message": (
                    "A script's object_id must not be one of "
                    "reload, toggle, turn_off, turn_on"
                ),
                "path": [],
                "code": "in_list",
                "translation_key": "value_not_one_of",
                "translation_domain": None,
                "translation_placeholders": {
                    "values": ["reload", "toggle", "turn_off", "turn_on"]
                },
            }
        ],
    }

    new_data = hass_config_store["scripts.yaml"]
    assert new_data == {}


_UNKNOWN_ENTITY_CONDITION = {
    "condition": "state",
    # The UUID will fail being resolved to an entity_id
    "entity_id": "abcdabcdabcdabcdabcdabcdabcdabcd",
    "state": "blah",
}

_INVALID_CONFIGS = [
    pytest.param({}, id="missing_key"),
    pytest.param({"sequence": _UNKNOWN_ENTITY_CONDITION}, id="single_action"),
    pytest.param(
        {
            "sequence": [{"delay": "abc"}, {"delay": 1, "bogus": 2}],
            "mode": "bogus",
        },
        id="schema_errors",
    ),
    pytest.param(
        {
            "sequence": [
                {"delay": 1},
                _UNKNOWN_ENTITY_CONDITION,
                {"wait_for_trigger": [{"trigger": "state"}]},
            ],
        },
        id="platform_errors",
    ),
    pytest.param(
        {"sequence": {"wait_for_trigger": {"trigger": "state"}}},
        id="single_items",
    ),
    pytest.param(
        {
            "sequence": [
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
                },
                {"parallel": [{"delay": 1}, [_UNKNOWN_ENTITY_CONDITION]]},
            ],
        },
        id="nested_blocks",
    ),
    pytest.param(
        {
            "sequence": [
                {"delay": "abc"},
                _UNKNOWN_ENTITY_CONDITION,
                {"wait_for_trigger": [{"trigger": "automation"}]},
            ],
        },
        id="schema_and_platform_errors",
    ),
    pytest.param(
        {
            "sequence": [_UNKNOWN_ENTITY_CONDITION],
            "mode": "bogus",
            "fields": {"brightness": {"required": "maybe"}},
        },
        id="schema_errors_outside_sequence_and_platform_error",
    ),
    pytest.param(
        {"alias": "Moon", "mode": "bogus"},
        id="missing_key_and_schema_error",
    ),
]
_INVALID_BLUEPRINT_CONFIGS = [
    pytest.param(
        {
            "use_blueprint": {
                "path": "test_service.yaml",
                "input": {"service_to_call": 5},
            },
        },
        id="blueprint_generated_config_error",
    ),
    pytest.param(
        {
            "alias": "Blueprint script",
            "mode": "bogus",
            "use_blueprint": {
                "path": "test_service.yaml",
                "input": {"service_to_call": "test.automation"},
            },
        },
        id="blueprint_instance_key_error",
    ),
    pytest.param(
        {
            "mode": "bogus",
            "use_blueprint": {
                "path": "test_service.yaml",
                "input": {"service_to_call": 5},
            },
        },
        id="blueprint_instance_key_and_generated_config_errors",
    ),
]


@pytest.mark.parametrize("script_config", [{}])
@pytest.mark.parametrize(
    "updated_config",
    [
        *_INVALID_CONFIGS,
        *_INVALID_BLUEPRINT_CONFIGS,
        pytest.param(
            {"use_blueprint": {"path": "test_service.yaml", "input": {}}},
            id="blueprint_missing_input",
        ),
        pytest.param(
            {"use_blueprint": {"path": "not_found.yaml", "input": {}}},
            id="blueprint_not_found",
        ),
    ],
)
async def test_update_script_config_with_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_config_store: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
    snapshot: SnapshotAssertion,
    updated_config: dict[str, Any],
) -> None:
    """Test updating script config with errors."""
    with patch.object(config, "SECTIONS", [script]):
        await async_setup_component(hass, DOMAIN, {})

    assert sorted(hass.states.async_entity_ids("script")) == []

    client = await hass_client()

    orig_data = {"sun": {}, "moon": {}}
    hass_config_store["scripts.yaml"] = orig_data

    resp = await client.post(
        "/api/config/script/config/moon",
        data=json.dumps(updated_config),
    )
    await hass.async_block_till_done()
    assert sorted(hass.states.async_entity_ids("script")) == []

    assert resp.status == HTTPStatus.BAD_REQUEST
    result = await resp.json()
    assert result == snapshot
    assert_error_paths_resolve(updated_config, result["errors"])
    assert hass_config_store["scripts.yaml"] == {"sun": {}, "moon": {}}
    # Assert the validation error is not logged
    assert result["message"].removeprefix("Message malformed: ") not in caplog.text


@pytest.mark.parametrize("script_config", [{}])
@pytest.mark.parametrize("config", _INVALID_CONFIGS)
def test_block_schema_errors_match_script_schema(config: dict[str, Any]) -> None:
    """Test the schema of the sequence gives the errors the script schema gives for it.

    The errors of the sequence are reported once because they are the same.
    """
    assert_block_schema_errors_match(
        script_validation.SCRIPT_ENTITY_SCHEMA, _BLOCK_KINDS, config
    )


@pytest.mark.parametrize("script_config", [{}])
@pytest.mark.parametrize("config", _INVALID_BLUEPRINT_CONFIGS)
async def test_block_schema_errors_match_script_schema_blueprint(
    hass: HomeAssistant, config: dict[str, Any]
) -> None:
    """Test the same for the config which is generated from a blueprint."""
    blueprint_inputs = await async_get_blueprints(hass).async_inputs_from_config(config)

    assert_block_schema_errors_match(
        script_validation.SCRIPT_ENTITY_SCHEMA,
        _BLOCK_KINDS,
        blueprint_inputs.async_substitute(),
    )


@pytest.mark.parametrize("script_config", [{}])
@pytest.mark.parametrize(
    ("config_key", "data", "message"),
    [
        pytest.param("moon", "not json", "Invalid JSON specified", id="invalid_json"),
        pytest.param(
            "Bad Key",
            json.dumps({"sequence": [{"delay": "abc"}]}),
            "Key malformed: invalid slug Bad Key (try bad_key)",
            id="key_malformed",
        ),
    ],
)
async def test_update_script_config_error_without_errors(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_config_store: dict[str, Any],
    config_key: str,
    data: str,
    message: str,
) -> None:
    """Test the errors which are not about the config have no list of errors."""
    with patch.object(config, "SECTIONS", [script]):
        await async_setup_component(hass, DOMAIN, {})

    client = await hass_client()

    resp = await client.post(f"/api/config/script/config/{config_key}", data=data)

    assert resp.status == HTTPStatus.BAD_REQUEST
    assert await resp.json() == {"message": message}


@pytest.mark.parametrize("script_config", [{}])
@pytest.mark.parametrize(
    ("updated_config", "validation_error"),
    [
        (
            {
                "use_blueprint": {
                    "path": "test_service.yaml",
                    "input": {
                        "service_to_call": "test.automation",
                    },
                },
            },
            "No substitution found for input blah",
        ),
    ],
)
async def test_update_script_config_with_blueprint_substitution_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_config_store: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
    updated_config: Any,
    validation_error: str,
) -> None:
    """Test updating script config with errors."""
    with patch.object(config, "SECTIONS", [script]):
        await async_setup_component(hass, DOMAIN, {})

    assert sorted(hass.states.async_entity_ids("script")) == []

    client = await hass_client()

    orig_data = {"sun": {}, "moon": {}}
    hass_config_store["scripts.yaml"] = orig_data

    with patch(
        "homeassistant.components.blueprint.models.BlueprintInputs.async_substitute",
        side_effect=yaml_util.UndefinedSubstitution("blah"),
    ):
        resp = await client.post(
            "/api/config/script/config/moon",
            data=json.dumps(updated_config),
        )
        await hass.async_block_till_done()
    assert sorted(hass.states.async_entity_ids("script")) == []

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


@pytest.mark.parametrize("script_config", [{}])
async def test_update_script_config_error_not_found_again(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_config_store: dict[str, Any],
) -> None:
    """Test the error is kept if validating again does not give any error."""
    with patch.object(config, "SECTIONS", [script]):
        await async_setup_component(hass, DOMAIN, {})

    client = await hass_client()

    hass_config_store["scripts.yaml"] = {"sun": {}, "moon": {}}

    with patch(
        "homeassistant.components.script.config._async_collect_errors",
        return_value=[],
    ):
        resp = await client.post(
            "/api/config/script/config/moon",
            data=json.dumps(
                {"sequence": {"wait_for_trigger": {"trigger": "automation"}}}
            ),
        )

    assert resp.status == HTTPStatus.BAD_REQUEST
    # The path is the one in the validated config
    assert await resp.json() == {
        "message": (
            "Message malformed: Integration 'automation' does not provide trigger support at 'sequence[0].wait_for_trigger[0]'"
        ),
        "errors": [
            {
                "message": "Integration 'automation' does not provide trigger support",
                "path": ["sequence", 0, "wait_for_trigger", 0],
                "code": None,
                "translation_key": None,
                "translation_domain": None,
                "translation_placeholders": {},
            }
        ],
    }


@pytest.mark.parametrize("script_config", [{}])
async def test_validate_config_item_clears_traceback(hass: HomeAssistant) -> None:
    """Test the traceback of the first error is cleared when other errors are raised."""
    fail_fast_error = probatio.Invalid("fail fast")

    with (
        patch(
            "homeassistant.components.script.config._async_validate_config_item",
            side_effect=fail_fast_error,
        ),
        pytest.raises(ValidationErrors) as exc_info,
    ):
        await script_validation.async_validate_config_item(
            hass, "moon", {"sequence": [{"wait_for_trigger": [{"trigger": "state"}]}]}
        )

    assert fail_fast_error not in [info.exception for info in exc_info.value.errors]
    assert fail_fast_error.__traceback__ is None


@pytest.mark.parametrize("script_config", [{}])
async def test_update_remove_key_script_config(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_config_store: dict[str, Any],
) -> None:
    """Test updating script config while removing a key."""
    with patch.object(config, "SECTIONS", [script]):
        await async_setup_component(hass, DOMAIN, {})

    assert sorted(hass.states.async_entity_ids("script")) == []

    client = await hass_client()

    orig_data = {"sun": {"key": "value"}, "moon": {"key": "value"}}
    hass_config_store["scripts.yaml"] = orig_data

    resp = await client.post(
        "/api/config/script/config/moon",
        data=json.dumps({"sequence": []}),
    )
    await hass.async_block_till_done()
    assert sorted(hass.states.async_entity_ids("script")) == [
        "script.moon",
        "script.sun",
    ]
    assert hass.states.get("script.moon").state == STATE_OFF
    assert hass.states.get("script.sun").state == STATE_UNAVAILABLE

    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"result": "ok"}

    new_data = hass_config_store["scripts.yaml"]
    assert list(new_data["moon"]) == ["sequence"]
    assert new_data["moon"] == {"sequence": []}


@pytest.mark.parametrize(
    "script_config",
    [
        {
            "one": {"alias": "Light on", "sequence": []},
            "two": {"alias": "Light off", "sequence": []},
        },
    ],
)
async def test_delete_script(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
    hass_config_store: dict[str, Any],
) -> None:
    """Test deleting a script."""
    with patch.object(config, "SECTIONS", [script]):
        await async_setup_component(hass, DOMAIN, {})

    assert sorted(hass.states.async_entity_ids("script")) == [
        "script.one",
        "script.two",
    ]

    assert len(entity_registry.entities) == 2

    client = await hass_client()

    orig_data = {"one": {}, "two": {}}
    hass_config_store["scripts.yaml"] = orig_data

    resp = await client.delete("/api/config/script/config/two")
    await hass.async_block_till_done()

    assert sorted(hass.states.async_entity_ids("script")) == [
        "script.one",
    ]

    assert resp.status == HTTPStatus.OK
    result = await resp.json()
    assert result == {"result": "ok"}

    assert hass_config_store["scripts.yaml"] == {"one": {}}

    assert len(entity_registry.entities) == 1


@pytest.mark.parametrize("script_config", [{}])
async def test_api_calls_require_admin(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_read_only_access_token: str,
    hass_config_store: dict[str, Any],
) -> None:
    """Test script APIs endpoints do not work as a normal user."""
    with patch.object(config, "SECTIONS", [script]):
        await async_setup_component(hass, DOMAIN, {})

    hass_config_store["scripts.yaml"] = {
        "moon": {"alias": "Moon"},
    }

    client = await hass_client(hass_read_only_access_token)

    # Get
    resp = await client.get("/api/config/script/config/moon")
    assert resp.status == HTTPStatus.UNAUTHORIZED

    # Update
    resp = await client.post(
        "/api/config/script/config/moon",
        data=json.dumps({"sequence": []}),
    )
    assert resp.status == HTTPStatus.UNAUTHORIZED

    # Delete
    resp = await client.delete("/api/config/script/config/moon")
    assert resp.status == HTTPStatus.UNAUTHORIZED
