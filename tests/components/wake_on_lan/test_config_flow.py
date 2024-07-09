"""Test the Scrape config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant import config_entries
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.wake_on_lan.const import CONF_OFF_ACTION, DOMAIN
from homeassistant.const import (
    CONF_BROADCAST_ADDRESS,
    CONF_BROADCAST_PORT,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    STATE_OFF,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from .conftest import DEFAULT_MAC

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_MAC: DEFAULT_MAC,
            CONF_HOST: "192.168.10.10",
            CONF_OFF_ACTION: [{"service: wake_on_lan.send_magic_packet"}],
            CONF_BROADCAST_ADDRESS: "255.255.255.255",
            CONF_BROADCAST_PORT: 9,
        },
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["version"] == 1
    assert result["options"] == {
        CONF_MAC: DEFAULT_MAC,
        CONF_HOST: "192.168.10.10",
        CONF_OFF_ACTION: [{"service: wake_on_lan.send_magic_packet"}],
        CONF_BROADCAST_ADDRESS: "255.255.255.255",
        CONF_BROADCAST_PORT: 9,
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_options_flow(hass: HomeAssistant, loaded_entry: MockConfigEntry) -> None:
    """Test options flow."""

    result = await hass.config_entries.options.async_init(loaded_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "192.168.10.10",
            CONF_OFF_ACTION: [{"service: wake_on_lan.send_magic_packet"}],
            CONF_BROADCAST_ADDRESS: "255.255.255.255",
            CONF_BROADCAST_PORT: 10,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_MAC: DEFAULT_MAC,
        CONF_HOST: "192.168.10.10",
        CONF_OFF_ACTION: [{"service: wake_on_lan.send_magic_packet"}],
        CONF_BROADCAST_ADDRESS: "255.255.255.255",
        CONF_BROADCAST_PORT: 10,
    }

    await hass.async_block_till_done()

    # Check the entity was updated, no new entity was created
    assert len(hass.states.async_all()) == 1

    state = hass.states.get("switch.wake_on_lan_00_01_02_03_04_05_06")
    assert state is not None


async def test_entry_already_exist(
    hass: HomeAssistant, loaded_entry: MockConfigEntry
) -> None:
    """Test abort when entry already exist."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "user"
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_MAC: DEFAULT_MAC,
            CONF_HOST: "192.168.10.10",
            CONF_OFF_ACTION: [{"service: wake_on_lan.send_magic_packet"}],
            CONF_BROADCAST_ADDRESS: "255.255.255.255",
            CONF_BROADCAST_PORT: 9,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import(hass: HomeAssistant, mock_send_magic_packet: AsyncMock) -> None:
    """Test importing."""

    assert await async_setup_component(
        hass,
        SWITCH_DOMAIN,
        {
            "switch": {
                "platform": "wake_on_lan",
                "name": "Test WOL",
                "mac": DEFAULT_MAC,
                "scan_interval": 60,
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.test_wol")
    assert state.state == STATE_OFF

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry
    assert entry.title == "Test WOL"
    assert entry.data == {}
    assert entry.options == {
        CONF_MAC: DEFAULT_MAC,
        CONF_NAME: "Test WOL",
    }
