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

COMMAND_INPUT = {
    "action": "Open door",
    "url": TEST_URL + "{{ door }}",
    "method": "post",
    "payload": '{"open": true}',
    "auth": {"username": "user", "password": "secret"},
    "additional": {
        "headers": {"X-Door": "{{ door }}"},
        "timeout": 5.0,
        "verify_ssl": False,
    },
}

COMMAND_DATA = {
    "action": "open_door",
    "url": TEST_URL + "{{ door }}",
    "method": "post",
    "payload": '{"open": true}',
    "username": "user",
    "password": "secret",
    "headers": {"X-Door": "{{ door }}"},
    "timeout": 5,
    "verify_ssl": False,
    "insecure_cipher": False,
    "skip_url_encoding": False,
}


@pytest.fixture
def entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a config entry with one command."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="RESTful Command",
        subentries_data=[
            ConfigSubentryData(
                data=COMMAND_DATA,
                subentry_type=SUBENTRY_TYPE_COMMAND,
                title="open_door",
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
    """Test creating the entry and the first command."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "RESTful Command"
    assert result["data"] == {}
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


async def test_single_instance(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Test only one entry can be created."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


@pytest.mark.parametrize(
    ("user_input", "errors"),
    [
        ({"action": " "}, {"action": "invalid_action"}),
        ({"action": "Reload"}, {"action": "invalid_action"}),
        ({"action": "Open door"}, {"action": "action_exists"}),
        ({"auth": {"username": "user"}}, {"base": "invalid_command"}),
    ],
)
async def test_subentry_errors(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    user_input: dict[str, Any],
    errors: dict[str, str],
) -> None:
    """Test the errors of the command flow, and recovering from them."""
    result = await _start_subentry_flow(hass, entry)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "action": "New command",
            "url": TEST_URL,
            "method": "get",
            "auth": {},
            "additional": {},
            **user_input,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == errors

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "action": "New command",
            "url": TEST_URL,
            "method": "get",
            "auth": {},
            "additional": {},
        },
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
    hass: HomeAssistant, entry: MockConfigEntry, auth: dict[str, str]
) -> None:
    """Test an explicitly empty username or password is stored, like in YAML."""
    result = await _start_subentry_flow(hass, entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "action": "New command",
            "url": TEST_URL,
            "method": "get",
            "auth": auth,
            "additional": {},
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert {key: result["data"][key] for key in auth} == auth


async def test_action_from_yaml_exists(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test a command cannot take the action name of a command from YAML."""
    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {"from_yaml": {"url": TEST_URL}}}
    )
    result = await _start_subentry_flow(hass, entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "action": "From YAML",
            "url": TEST_URL,
            "method": "get",
            "auth": {},
            "additional": {},
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"action": "action_exists"}

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "action": "From UI",
            "url": TEST_URL,
            "method": "get",
            "auth": {},
            "additional": {},
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
