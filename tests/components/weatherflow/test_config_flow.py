"""Tests for WeatherFlow."""

import asyncio
from unittest.mock import AsyncMock, patch

from pyweatherflowudp.errors import AddressInUseError

from homeassistant import config_entries
from homeassistant.components.weatherflow.const import (
    DOMAIN,
    ERROR_MSG_ADDRESS_IN_USE,
    ERROR_MSG_CANNOT_CONNECT,
    ERROR_MSG_NO_DEVICE_FOUND,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_single_instance(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_has_devices: AsyncMock,
) -> None:
    """Test more than one instance."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_devices_with_mocks(
    hass: HomeAssistant, mock_start: AsyncMock, mock_stop: AsyncMock
) -> None:
    """Test getting user input."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {}


async def test_devices_with_various_mocks_errors(
    hass: HomeAssistant,
    mock_start: AsyncMock,
    mock_stop: AsyncMock,
) -> None:
    """Test the various on error states - then finally complete the test."""

    with patch(
        "homeassistant.components.weatherflow.config_flow.WeatherFlowListener.on",
        side_effect=asyncio.TimeoutError,
        return_value=None,
    ):
        result1 = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

        await hass.async_block_till_done()
        assert result1["type"] == FlowResultType.FORM
        assert result1["errors"]["base"] == ERROR_MSG_NO_DEVICE_FOUND
        assert result1["step_id"] == "user"

    with patch(
        "homeassistant.components.weatherflow.config_flow.WeatherFlowListener.on",
        side_effect=asyncio.exceptions.CancelledError,
    ):
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        await hass.async_block_till_done()
        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"]["base"] == ERROR_MSG_CANNOT_CONNECT
        assert result2["step_id"] == "user"

    with patch(
        "homeassistant.components.weatherflow.config_flow.WeatherFlowListener.on",
        side_effect=AddressInUseError,
    ):
        result3 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        await hass.async_block_till_done()
        assert result3["type"] == FlowResultType.FORM
        assert result3["errors"]["base"] == ERROR_MSG_ADDRESS_IN_USE
        assert result3["step_id"] == "user"

    result4 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    await hass.async_block_till_done()
    assert result4["type"] == FlowResultType.CREATE_ENTRY
    assert result4["data"] == {}
