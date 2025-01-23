"""Test the Scrape config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant import config_entries
from homeassistant.components.wake_on_lan.const import DOMAIN
from homeassistant.const import CONF_BROADCAST_ADDRESS, CONF_BROADCAST_PORT, CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

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
            CONF_BROADCAST_ADDRESS: "255.255.255.255",
            CONF_BROADCAST_PORT: 9,
        },
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["version"] == 1
    assert result["options"] == {
        CONF_MAC: DEFAULT_MAC,
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
            CONF_BROADCAST_ADDRESS: "192.168.255.255",
            CONF_BROADCAST_PORT: 10,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_MAC: DEFAULT_MAC,
        CONF_BROADCAST_ADDRESS: "192.168.255.255",
        CONF_BROADCAST_PORT: 10,
    }

    await hass.async_block_till_done()

    assert loaded_entry.options == {
        CONF_MAC: DEFAULT_MAC,
        CONF_BROADCAST_ADDRESS: "192.168.255.255",
        CONF_BROADCAST_PORT: 10,
    }

    # Check the entity was updated, no new entity was created
    assert len(hass.states.async_all()) == 1

    state = hass.states.get("button.wake_on_lan_00_01_02_03_04_05")
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
            CONF_BROADCAST_ADDRESS: "255.255.255.255",
            CONF_BROADCAST_PORT: 9,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
