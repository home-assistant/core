"""Tests for the AirGradient integration."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.everhome.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_platform

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_connection_failed(
    hass: HomeAssistant,
    mock_everhome_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device registry integration."""
    mock_everhome_client.async_update.return_value = False
    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.unique_id)}
    )
    assert device_entry is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_coordinator_connection_failed(
    hass: HomeAssistant,
    mock_everhome_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator update failed."""
    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.unique_id)}
    )
    assert device_entry is not None

    config_entry_id = next(iter(device_entry.config_entries))
    config_entry = hass.config_entries.async_get_entry(config_entry_id)
    assert config_entry.runtime_data.last_update_success

    mock_everhome_client.async_update.return_value = False

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert not config_entry.runtime_data.last_update_success
