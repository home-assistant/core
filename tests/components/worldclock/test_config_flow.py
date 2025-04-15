"""Test the Worldclock config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant import config_entries
from homeassistant.components.worldclock.const import (
    CONF_TIME_FORMAT,
    DEFAULT_NAME,
    DEFAULT_TIME_STR_FORMAT,
    DOMAIN,
)
from homeassistant.const import CONF_NAME, CONF_TIME_ZONE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

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
            CONF_NAME: DEFAULT_NAME,
            CONF_TIME_ZONE: "America/New_York",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["version"] == 1
    assert result["options"] == {
        CONF_NAME: DEFAULT_NAME,
        CONF_TIME_ZONE: "America/New_York",
        CONF_TIME_FORMAT: DEFAULT_TIME_STR_FORMAT,
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
            CONF_TIME_FORMAT: "%a, %b %d, %Y %I:%M %p",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_NAME: DEFAULT_NAME,
        CONF_TIME_ZONE: "America/New_York",
        CONF_TIME_FORMAT: "%a, %b %d, %Y %I:%M %p",
    }

    await hass.async_block_till_done()

    # Check the entity was updated, no new entity was created
    assert len(hass.states.async_all()) == 1

    state = hass.states.get("sensor.worldclock_sensor")
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
            CONF_NAME: DEFAULT_NAME,
            CONF_TIME_ZONE: "America/New_York",
            CONF_TIME_FORMAT: DEFAULT_TIME_STR_FORMAT,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
