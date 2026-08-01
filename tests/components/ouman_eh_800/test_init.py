"""Test the Ouman EH-800 setup."""

from unittest.mock import AsyncMock

from ouman_eh_800_api import (
    OumanClientAuthenticationError,
    OumanClientCommunicationError,
)
import pytest

from homeassistant.components.ouman_eh_800.const import DOMAIN, OumanDevice
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_ouman_client")
async def test_sub_devices_link_to_main_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that the L1/L2 sub-devices link to the main device via via_device_id."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    entry_id = mock_config_entry.entry_id
    main_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, entry_id), config_entry_id=entry_id
    )
    assert main_device is not None

    for sub_device in (OumanDevice.L1, OumanDevice.L2):
        device = device_registry.async_get_device_by_identifier(
            (DOMAIN, f"{entry_id}_{sub_device}"), config_entry_id=entry_id
        )
        assert device is not None
        assert device.via_device_id == main_device.id


@pytest.mark.usefixtures("mock_ouman_client")
async def test_setup_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config entry setup and unload."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("error", "expected_state"),
    [
        (
            OumanClientCommunicationError("Connection failed"),
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            OumanClientAuthenticationError("Invalid credentials"),
            ConfigEntryState.SETUP_ERROR,
        ),
    ],
)
async def test_setup_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ouman_client: AsyncMock,
    error: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test that setup raises the correct config-entry exception on client errors."""
    mock_ouman_client.login.side_effect = error
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is expected_state
