"""Tests for config/script."""

from http import HTTPStatus
import json
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.bootstrap import async_setup_component
from homeassistant.components import config
from homeassistant.components.config import script
from homeassistant.const import STATE_OFF, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import yaml

from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


@pytest.fixture(autouse=True)
async def setup_script(hass, script_config, stub_blueprint_populate):
    """Set up script integration."""
    assert await async_setup_component(hass, "script", {"script": script_config})


@pytest.mark.parametrize("script_config", [{}])
async def test_get_script_config(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, hass_config_store
) -> None:
    """Test getting script config."""
    with patch.object(config, "SECTIONS", [script]):
        await async_setup_component(hass, "config", {})

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
    hass: HomeAssistant, hass_client: ClientSessionGenerator, hass_config_store
) -> None:
    """Test updating script config."""
    with patch.object(config, "SECTIONS", [script]):
        await async_setup_component(hass, "config", {})

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
async def test_invalid_object_id(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, hass_config_store
) -> None:
    """Test creating a script with an invalid object_id."""
    with patch.object(config, "SECTIONS", [script]):
        await async_setup_component(hass, "config", {})

    assert sorted(hass.states.async_entity_ids("script")) == []

    client = await hass_client()

    hass_config_store["scripts.yaml"] = {}

    resp = await client.post(
        "/api/config/script/config/turn_on",
        data=json.dumps({"alias": "Turn on", "sequence": []}),
    )
    await hass.async_block_till_done()
    assert sorted(hass.states.async_entity_ids("script")) == []

    assert resp.status == HTTPStatus.BAD_REQUEST
    result = await resp.json()
    assert result == {
        "message": (
            "Message malformed: A script's object_id must not be one of "
            "reload, toggle, turn_off, turn_on"
        )
    }

    new_data = hass_config_store["scripts.yaml"]
    assert new_data == {}


@pytest.mark.parametrize("script_config", [{}])
@pytest.mark.parametrize(
    ("updated_config", "validation_error"),
    [
        ({}, "required key not provided @ data['sequence']"),
        (
            {
                "sequence": {
                    "condition": "state",
                    # The UUID will fail being resolved to en entity_id
                    "entity_id": "abcdabcdabcdabcdabcdabcdabcdabcd",
                    "state": "blah",
                }
            },
            "Unknown entity registry entry abcdabcdabcdabcdabcdabcdabcdabcd",
        ),
        (
            {
                "use_blueprint": {
                    "path": "test_service.yaml",
                    "input": {},
                },
            },
            "Missing input service_to_call",
        ),
    ],
)
async def test_update_script_config_with_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_config_store,
    caplog: pytest.LogCaptureFixture,
    updated_config: Any,
    validation_error: str,
) -> None:
    """Test updating script config with errors."""
    with patch.object(config, "SECTIONS", [script]):
        await async_setup_component(hass, "config", {})

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

    assert resp.status != HTTPStatus.OK
    result = await resp.json()
    assert result == {"message": f"Message malformed: {validation_error}"}
    # Assert the validation error is not logged
    assert validation_error not in caplog.text


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
    hass_config_store,
    # setup_automation,
    caplog: pytest.LogCaptureFixture,
    updated_config: Any,
    validation_error: str,
) -> None:
    """Test updating script config with errors."""
    with patch.object(config, "SECTIONS", [script]):
        await async_setup_component(hass, "config", {})

    assert sorted(hass.states.async_entity_ids("script")) == []

    client = await hass_client()

    orig_data = {"sun": {}, "moon": {}}
    hass_config_store["scripts.yaml"] = orig_data

    with patch(
        "homeassistant.components.blueprint.models.BlueprintInputs.async_substitute",
        side_effect=yaml.UndefinedSubstitution("blah"),
    ):
        resp = await client.post(
            "/api/config/script/config/moon",
            data=json.dumps(updated_config),
        )
        await hass.async_block_till_done()
    assert sorted(hass.states.async_entity_ids("script")) == []

    assert resp.status != HTTPStatus.OK
    result = await resp.json()
    assert result == {"message": f"Message malformed: {validation_error}"}
    # Assert the validation error is not logged
    assert validation_error not in caplog.text


@pytest.mark.parametrize("script_config", [{}])
async def test_update_remove_key_script_config(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, hass_config_store
) -> None:
    """Test updating script config while removing a key."""
    with patch.object(config, "SECTIONS", [script]):
        await async_setup_component(hass, "config", {})

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
    hass_config_store,
) -> None:
    """Test deleting a script."""
    with patch.object(config, "SECTIONS", [script]):
        await async_setup_component(hass, "config", {})

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
    hass_config_store,
) -> None:
    """Test script APIs endpoints do not work as a normal user."""
    with patch.object(config, "SECTIONS", [script]):
        await async_setup_component(hass, "config", {})

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
