"""Tests for the Alexa Devices integration."""

from collections.abc import Mapping
from unittest.mock import AsyncMock

from aioamazondevices.structures import AmazonDevice
from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.alexa_devices.coordinator import SCAN_INTERVAL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def assert_device_removed_and_readded(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_amazon_devices_client: AsyncMock,
    config_entry: MockConfigEntry,
    entity_id: str,
    devices_with: Mapping[str, AmazonDevice],
    devices_without: Mapping[str, AmazonDevice],
) -> None:
    """Assert an entity is recreated when its device is removed and re-added."""
    mock_amazon_devices_client.get_devices_data.return_value = dict(devices_with)
    await setup_integration(hass, config_entry)

    assert hass.states.get(entity_id) is not None

    mock_amazon_devices_client.get_devices_data.return_value = dict(devices_without)
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id) is None

    mock_amazon_devices_client.get_devices_data.return_value = dict(devices_with)
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id) is not None
