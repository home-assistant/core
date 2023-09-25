"""Tests for weatherflow."""

import asyncio
from unittest.mock import AsyncMock, patch

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


async def test_address_in_use(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_has_devices_error_address_in_use: AsyncMock,
) -> None:
    """Test the address in use error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["errors"]["base"] == ERROR_MSG_ADDRESS_IN_USE
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.weatherflow.config_flow._async_can_discover_devices",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["data"] == {}


async def test_cannot_connect(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_has_devices_error_listener_error: AsyncMock,
) -> None:
    """Test the address in use error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["errors"]["base"] == ERROR_MSG_CANNOT_CONNECT
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.weatherflow.config_flow._async_can_discover_devices",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["data"] == {}


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


async def test_devices_with_mocks_timeout(
    hass: HomeAssistant,
    mock_start_timeout: AsyncMock,
    mock_stop: AsyncMock,
    mock_on_throws_timeout: AsyncMock,
) -> None:
    """Test a timeout on discovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == ERROR_MSG_NO_DEVICE_FOUND
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.weatherflow.config_flow._async_can_discover_devices",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["data"] == {}


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

    result3 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    await hass.async_block_till_done()
    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["data"] == {}
