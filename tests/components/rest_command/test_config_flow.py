"""Tests for the REST command config flow."""

from typing import Any

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.rest_command.const import DOMAIN, SUBENTRY_TYPE_COMMAND
from homeassistant.config_entries import SOURCE_USER, ConfigSubentryData
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from .conftest import TEST_URL

SERVER_URL = "https://example.com"

SERVER_INPUT = {
    "url": SERVER_URL + "/",
    "auth": {"username": "user", "password": "secret"},
    "additional": {
        "headers": {"X-Api-Version": "2"},
        "timeout": 5.0,
        "verify_ssl": False,
    },
}

SERVER_DATA = {
    "url": SERVER_URL,
    "auth": {"username": "user", "password": "secret"},
    "additional": {
        "headers": {"X-Api-Version": "2"},
        "timeout": 5.0,
        "verify_ssl": False,
        "insecure_cipher": False,
    },
}

COMMAND_INPUT = {
    "name": "Open door",
    "path": "door/{{ door }}",
    "method": "post",
    "payload": '{"open": true}',
    "additional": {"content_type": "application/json"},
}

COMMAND_DATA = {
    "path": "/door/{{ door }}",
    "method": "post",
    "payload": '{"open": true}',
    "additional": {"content_type": "application/json", "skip_url_encoding": False},
}

NEW_COMMAND_INPUT = {"name": "New command", "method": "get", "additional": {}}


@pytest.fixture
def entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a config entry for a server with one command."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=SERVER_URL,
        data={"url": SERVER_URL},
        subentries_data=[
            ConfigSubentryData(
                data=COMMAND_DATA,
                subentry_type=SUBENTRY_TYPE_COMMAND,
                title="Open door",
            )
        ],
    )
    entry.add_to_hass(hass)
    return entry


async def _start_subentry_flow(
    hass: HomeAssistant, entry: MockConfigEntry
) -> dict[str, Any]:
    return await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_COMMAND),
        context={"source": SOURCE_USER},
    )


async def test_full_flow(hass: HomeAssistant) -> None:
    """Test adding a server and its first command."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], SERVER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == SERVER_URL
    assert result["data"] == SERVER_DATA
    entry = result["result"]

    subentry_flows = hass.config_entries.subentries.async_progress()
    assert len(subentry_flows) == 1
    assert result["next_flow"][1] == subentry_flows[0]["flow_id"]

    result = await hass.config_entries.subentries.async_configure(
        subentry_flows[0]["flow_id"], COMMAND_INPUT
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Open door"
    assert result["data"] == COMMAND_DATA
    assert result["unique_id"] is None
    assert hass.services.has_service(DOMAIN, "open_door")
    assert len(entry.subentries) == 1


@pytest.mark.parametrize(
    ("user_input", "errors"),
    [
        ({"url": ""}, {"url": "invalid_url"}),
        ({"url": "example.com"}, {"url": "invalid_url"}),
        ({"url": "ftp://example.com"}, {"url": "invalid_url"}),
        ({"url": "https://"}, {"url": "invalid_url"}),
        ({"url": SERVER_URL + "/?key=1"}, {"url": "invalid_url"}),
        ({"url": SERVER_URL + "?"}, {"url": "invalid_url"}),
        ({"url": SERVER_URL + "#"}, {"url": "invalid_url"}),
        ({"url": "https://user:secret@example.com"}, {"url": "invalid_url"}),
        ({"url": "https://:secret@example.com"}, {"url": "invalid_url"}),
        ({"url": "http://["}, {"url": "invalid_url"}),
        ({"auth": {"username": "user"}}, {"base": "invalid_command"}),
    ],
)
async def test_server_errors(
    hass: HomeAssistant, user_input: dict[str, Any], errors: dict[str, str]
) -> None:
    """Test invalid server settings, and recovering from them."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"url": SERVER_URL, "auth": {}, "additional": {}, **user_input},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == errors

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"url": SERVER_URL, "auth": {}, "additional": {}}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_server_already_configured(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test a server can only be added once."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"url": SERVER_URL + "/", "auth": {}, "additional": {}}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("user_input", "errors"),
    [
        ({"name": " "}, {"name": "invalid_name"}),
        ({"name": "!!"}, {"name": "invalid_name"}),
        ({"name": "Reload"}, {"name": "invalid_name"}),
        ({"name": "Open door"}, {"name": "action_exists"}),
        ({"additional": {"headers": ["X-Door"]}}, {"base": "invalid_command"}),
        (
            {"additional": {"headers": {"X-Door": "{{ door"}}},
            {"base": "invalid_command"},
        ),
    ],
)
async def test_command_errors(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    user_input: dict[str, Any],
    errors: dict[str, str],
) -> None:
    """Test the errors of the command flow, and recovering from them."""
    result = await _start_subentry_flow(hass, entry)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {**NEW_COMMAND_INPUT, **user_input}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == errors

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], NEW_COMMAND_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize(
    "auth",
    [
        {"username": "user", "password": ""},
        {"username": "", "password": "token"},
    ],
)
async def test_empty_credential_is_kept(
    hass: HomeAssistant, auth: dict[str, str]
) -> None:
    """Test an explicitly empty username or password is stored, like in YAML."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"url": SERVER_URL, "auth": auth, "additional": {}}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["auth"] == auth


async def test_action_from_yaml_exists(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test a command cannot take the action name of a command from YAML."""
    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {"from_yaml": {"url": TEST_URL}}}
    )
    result = await _start_subentry_flow(hass, entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {**NEW_COMMAND_INPUT, "name": "From YAML"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"name": "action_exists"}

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], NEW_COMMAND_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
