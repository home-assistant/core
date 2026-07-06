"""Tests for the energieleser integration setup and unload."""

from unittest.mock import AsyncMock

from energieleser import (
    EnergieleserConnectionError,
    EnergieleserError,
    EnergieleserUnknownDeviceError,
)
import pytest

from homeassistant.components.energieleser.const import CONF_SW_VERSION, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE_ID, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import STROMLESER_DEVICE_ID, STROMLESER_SW_VERSION

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_energieleser_client")
async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_stromleser_config_entry: MockConfigEntry,
) -> None:
    """Test the config entry sets up and unloads cleanly."""
    mock_stromleser_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_stromleser_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_stromleser_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_stromleser_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_stromleser_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(EnergieleserConnectionError("boom"), id="connection_error"),
        pytest.param(
            EnergieleserUnknownDeviceError("unknown"), id="unknown_device_error"
        ),
        pytest.param(EnergieleserError("generic"), id="generic_error"),
    ],
)
async def test_setup_retries_on_client_error(
    hass: HomeAssistant,
    mock_energieleser_client: AsyncMock,
    mock_stromleser_config_entry: MockConfigEntry,
    side_effect: Exception,
) -> None:
    """Test the entry is retried when the client raises an error during setup."""
    mock_energieleser_client.get_device.side_effect = side_effect
    mock_stromleser_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(
        mock_stromleser_config_entry.entry_id
    )
    await hass.async_block_till_done()
    assert mock_stromleser_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_energieleser_client")
async def test_device_exposes_discovery_sw_version(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the firmware version captured at discovery is set on the device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_DEVICE_ID: STROMLESER_DEVICE_ID,
            CONF_SW_VERSION: STROMLESER_SW_VERSION,
        },
        unique_id=STROMLESER_DEVICE_ID,
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, STROMLESER_DEVICE_ID)}
    )
    assert device is not None
    assert device.sw_version == STROMLESER_SW_VERSION
