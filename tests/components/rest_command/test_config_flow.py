"""Tests for the REST command config flow."""

from typing import Any

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.rest_command.const import DOMAIN, SUBENTRY_TYPE_COMMAND
from homeassistant.config_entries import SOURCE_USER, ConfigSubentryData
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_URL

COMMAND_INPUT = {
    "action": "Open door",
    "url": TEST_URL + "{{ door }}",
    "method": "post",
    "payload": '{"open": true}',
    "auth": {"username": "user", "password": "secret"},
    "advanced": {
        "headers": {"X-Door": "{{ door }}"},
        "timeout": 5.0,
        "verify_ssl": False,
    },
}

COMMAND_DATA = {
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
                unique_id="open_door",
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
    assert result["unique_id"] == "open_door"
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
            "advanced": {},
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
            "advanced": {},
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_reconfigure(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Test changing a command keeps its action name."""
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    subentry_id = next(iter(entry.subentries))

    result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "url": TEST_URL,
            "method": "get",
            "auth": {"password": "secret"},
            "advanced": {},
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_command"}

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "url": TEST_URL,
            "method": "put",
            "auth": {},
            "advanced": {"timeout": 20},
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.subentries[subentry_id].data == {
        "url": TEST_URL,
        "method": "put",
        "timeout": 20,
        "verify_ssl": True,
        "insecure_cipher": False,
        "skip_url_encoding": False,
    }
    assert hass.services.has_service(DOMAIN, "open_door")


async def test_empty_password_is_kept(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Test an explicitly empty password is stored, like in YAML."""
    result = await _start_subentry_flow(hass, entry)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "action": "New command",
            "url": TEST_URL,
            "method": "get",
            "auth": {"username": "user", "password": ""},
            "advanced": {},
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["username"] == "user"
    assert result["data"]["password"] == ""
