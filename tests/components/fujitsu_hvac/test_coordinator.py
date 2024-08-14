"""Test for the FujitsuHVACCoordinator."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.fujitsu_hvac.const import API_REFRESH_SECONDS, DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_coordinator_one_device_disabled(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_devices: list[AsyncMock],
    mock_ayla_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that coordinator only updates devices that are currently listening."""
    await setup_integration(hass, mock_config_entry)

    for d in mock_devices:
        d.async_update.assert_called_once()
        d.reset_mock()

    entity = entity_registry.async_get(
        entity_registry.async_get_entity_id(
            Platform.CLIMATE, DOMAIN, mock_devices[0].device_serial_number
        )
    )
    entity_registry.async_update_entity(
        entity.entity_id, disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()
    freezer.tick(API_REFRESH_SECONDS)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == len(mock_devices) - 1
    mock_devices[0].async_update.assert_not_called()
    mock_devices[1].async_update.assert_called_once()
