"""Tests for the IOmeter integration."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from iometer import IOmeterConnectionError
import pytest

from homeassistant.components.iometer import async_setup_entry
from homeassistant.components.iometer.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from . import setup_platform

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_new_firmware_version(
    hass: HomeAssistant,
    mock_iometer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test device registry integration."""
    assert mock_config_entry.unique_id is not None

    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.unique_id)}
    )
    assert device_entry is not None
    assert device_entry.sw_version == "build-58/build-65"
    mock_iometer_client.get_current_status.return_value.device.core.version = "build-62"
    mock_iometer_client.get_current_status.return_value.device.bridge.version = (
        "build-69"
    )
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.unique_id)}
    )
    assert device_entry is not None
    assert device_entry.sw_version == "build-62/build-69"


async def test_async_setup_entry_connection_error(
    hass: HomeAssistant,
    mock_iometer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_setup_entry raises ConfigEntryNotReady on connection error."""

    mock_config_entry.add_to_hass(hass)
    mock_iometer_client.get_current_status.side_effect = IOmeterConnectionError(
        "cannot connect"
    )

    with pytest.raises(ConfigEntryNotReady):
        await async_setup_entry(hass, mock_config_entry)

    assert mock_iometer_client.get_current_status.await_count == 1
