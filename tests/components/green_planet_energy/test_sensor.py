"""Test the Green Planet Energy sensor."""

from freezegun.api import FrozenDateTimeFactory
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensors."""
    freezer.move_to("2024-01-01 13:00:00")
    await hass.async_block_till_done()
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


async def test_sensor_device_info(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test sensor device info."""
    entry = entity_registry.async_get("sensor.green_planet_energy_highest_price_today")

    assert entry is not None
    assert entry.device_id is not None

    device = device_registry.async_get(entry.device_id)

    assert device is not None
    assert device.name == "Green Planet Energy"
    assert device.entry_type is dr.DeviceEntryType.SERVICE
