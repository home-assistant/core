"""Tests for the SpaceAPI config flow."""

from http import HTTPStatus

from aiohttp.test_utils import TestClient

from homeassistant.components.spaceapi import (
    CONF_API_VERSION,
    CONF_CACHE,
    CONF_CONTACT,
    CONF_ISSUE_REPORT_CHANNELS,
    CONF_LOGO,
    CONF_SPACE,
    CONF_STATE,
    DOMAIN,
    SPACEAPI_VERSION,
    SPACEAPI_VERSION_15,
    URL_API_SPACEAPI,
)
from homeassistant.config_entries import (
    SOURCE_IMPORT,
    SOURCE_RECONFIGURE,
    SOURCE_USER,
    ConfigEntryState,
)
from homeassistant.const import CONF_EMAIL, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.issue_registry import IssueRegistry
from homeassistant.setup import async_setup_component

from tests.typing import ClientSessionGenerator

USER_INPUT = {
    CONF_SPACE: "Hackerspace",
    CONF_URL: "https://example.com",
    CONF_LOGO: "https://example.com/logo.png",
    CONF_EMAIL: "hello@example.com",
    "state_entity_id": "binary_sensor.space_open",
    CONF_ISSUE_REPORT_CHANNELS: ["email"],
    "optional": {
        "address": "Somewhere",
        "icon_open": "https://example.com/open.png",
        "icon_closed": "https://example.com/closed.png",
        "sensor_temperature": ["sensor.temperature"],
        "sensor_humidity": ["sensor.humidity"],
    },
}


async def test_form(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test the user config flow and API setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_VERSION: SPACEAPI_VERSION}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "configure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )
    assert result["type"] == "create_entry"
    assert result["title"] == "SpaceAPI"
    assert result["data"]["space"] == "Hackerspace"
    assert result["data"][CONF_STATE] == {
        "entity_id": "binary_sensor.space_open",
        "icon_open": "https://example.com/open.png",
        "icon_closed": "https://example.com/closed.png",
    }
    assert result["data"][CONF_CONTACT] == {CONF_EMAIL: "hello@example.com"}
    assert result["data"][CONF_API_VERSION] == SPACEAPI_VERSION
    assert result["data"]["sensors"] == {
        "temperature": ["sensor.temperature"],
        "humidity": ["sensor.humidity"],
    }

    entry = result["result"]
    assert entry.state is ConfigEntryState.LOADED

    client: TestClient = await hass_client()
    response = await client.get(URL_API_SPACEAPI)
    assert response.status == HTTPStatus.OK
    assert (await response.json())["space"] == "Hackerspace"

    assert await hass.config_entries.async_unload(entry.entry_id)
    response = await client.get(URL_API_SPACEAPI)
    assert response.status == HTTPStatus.SERVICE_UNAVAILABLE


async def test_duplicate_entry(hass: HomeAssistant) -> None:
    """Test only one SpaceAPI entry can be configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_VERSION: SPACEAPI_VERSION}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )
    assert result["type"] == "create_entry"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_import_yaml(hass: HomeAssistant, issue_registry: IssueRegistry) -> None:
    """Test existing YAML configuration is imported into a config entry."""
    yaml_config = {
        "space": "Hackerspace",
        CONF_URL: "https://example.com",
        CONF_LOGO: "https://example.com/logo.png",
        "contact": {CONF_EMAIL: "hello@example.com"},
        "issue_report_channels": ["email"],
        "state": {"entity_id": "binary_sensor.space_open"},
        "cache": {"schedule": "m.02"},
    }

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: yaml_config})
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].source == SOURCE_IMPORT
    assert entries[0].data == yaml_config | {CONF_API_VERSION: SPACEAPI_VERSION}
    assert entries[0].state is ConfigEntryState.LOADED
    assert issue_registry.async_get_issue(DOMAIN, "deprecated_yaml")


async def test_v15_removes_deprecated_fields(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test v15 warns and confirms removal of unsupported v13 fields."""
    old_config = {
        **USER_INPUT,
    }
    old_config["optional"] = {
        CONF_CACHE: {"schedule": "m.02"},
        "stream": {"m4": "https://example.com/stream"},
        "radio_show": [
            {
                "name": "Test",
                "url": "https://example.com/radio",
                "type": "ogg",
                "start": "2026-10-04T10:00Z",
                "end": "2026-10-04T12:00Z",
            }
        ],
        "contact_details": {"jabber": "chat@example.com"},
        "spacefed": {
            "spacenet": True,
            "spacesaml": False,
            "spacephone": True,
        },
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_VERSION: SPACEAPI_VERSION}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=old_config
    )
    assert result["type"] == "create_entry"

    entry = result["result"]
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_RECONFIGURE, "entry_id": entry.entry_id},
    )
    assert result["step_id"] == "reconfigure"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_VERSION: SPACEAPI_VERSION_15}
    )
    assert result["step_id"] == "configure"

    v15_input = {
        key: value
        for key, value in USER_INPUT.items()
        if key != CONF_ISSUE_REPORT_CHANNELS
    } | {
        "optional": {
            "address": "Somewhere",
            "contact_details": old_config["optional"]["contact_details"],
            "icon_open": "https://example.com/open.png",
            "icon_closed": "https://example.com/closed.png",
            "spacefed": old_config["optional"]["spacefed"],
        },
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=v15_input
    )
    assert result["type"] == "form"
    assert result["step_id"] == "confirm_v15"
    assert "cache" in result["description_placeholders"]["unsupported_items"]
    assert "contact.jabber" in result["description_placeholders"]["unsupported_items"]
    assert (
        "spacefed.spacephone" in result["description_placeholders"]["unsupported_items"]
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"confirm_removal": False}
    )
    assert result["type"] == "form"
    assert result["errors"]["base"] == "confirmation_required"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"confirm_removal": True}
    )
    assert result["type"] == "abort"
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_API_VERSION] == SPACEAPI_VERSION_15
    assert CONF_ISSUE_REPORT_CHANNELS not in entry.data
    assert CONF_CACHE not in entry.data
    assert "stream" not in entry.data
    assert "radio_show" not in entry.data
    assert "jabber" not in entry.data[CONF_CONTACT]
    assert entry.data["spacefed"] == {"spacenet": True, "spacesaml": False}

    client = await hass_client()
    response = await client.get(URL_API_SPACEAPI)
    assert response.status == HTTPStatus.OK
    data = await response.json()
    assert data["api_compatibility"] == ["14", SPACEAPI_VERSION_15]
    assert "api" not in data
    assert "issue_report_channels" not in data
    assert data["state"] == {
        "lastchange": 0,
        "icon": {
            "open": "https://example.com/open.png",
            "closed": "https://example.com/closed.png",
        },
    }


async def test_v15_requires_spacefed_fields(hass: HomeAssistant) -> None:
    """Test v15 requires both SpaceFED fields when that optional object is set."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_API_VERSION: SPACEAPI_VERSION_15}
    )
    user_input = USER_INPUT | {
        "optional": {"spacefed": {"spacenet": True}},
    }
    user_input.pop(CONF_ISSUE_REPORT_CHANNELS)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )
    assert result["type"] == "form"
    assert result["errors"]["base"] == "spacefed_required"
