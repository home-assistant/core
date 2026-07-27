"""The tests for Sense binary sensor platform."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from sense_energy import SenseAPIException
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.sense.const import ACTIVE_UPDATE_RATE, DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from . import setup_platform
from .const import DEVICE_1_ID, DEVICE_1_NAME, DEVICE_2_NAME, MONITOR_ID

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_binary_sensors(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test Sensor."""
    await setup_platform(hass, config_entry, Platform.BINARY_SENSOR)
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_on_off_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
) -> None:
    """Test the Sense binary sensors."""
    await setup_platform(hass, config_entry, BINARY_SENSOR_DOMAIN)
    device_1, device_2 = mock_sense.devices

    state = hass.states.get(f"binary_sensor.{DEVICE_1_NAME.lower()}_power")
    assert state.state == STATE_OFF

    state = hass.states.get(f"binary_sensor.{DEVICE_2_NAME.lower()}_power")
    assert state.state == STATE_OFF

    device_1.is_on = True
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=ACTIVE_UPDATE_RATE))
    await hass.async_block_till_done()

    state = hass.states.get(f"binary_sensor.{DEVICE_1_NAME.lower()}_power")
    assert state.state == STATE_ON

    state = hass.states.get(f"binary_sensor.{DEVICE_2_NAME.lower()}_power")
    assert state.state == STATE_OFF

    device_1.is_on = False
    device_2.is_on = True
    async_fire_time_changed(hass, utcnow() + timedelta(seconds=ACTIVE_UPDATE_RATE))
    await hass.async_block_till_done()

    state = hass.states.get(f"binary_sensor.{DEVICE_1_NAME.lower()}_power")
    assert state.state == STATE_OFF

    state = hass.states.get(f"binary_sensor.{DEVICE_2_NAME.lower()}_power")
    assert state.state == STATE_ON


async def test_realtime_update_exception(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that binary sensor entities become unavailable on realtime coordinator failure."""
    await setup_platform(hass, config_entry, Platform.BINARY_SENSOR)

    state = hass.states.get(f"binary_sensor.{DEVICE_1_NAME.lower()}_power")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    mock_sense.update_realtime.side_effect = SenseAPIException("api error")

    freezer.tick(timedelta(seconds=ACTIVE_UPDATE_RATE))
    async_fire_time_changed(hass, freezer())
    await hass.async_block_till_done()

    state = hass.states.get(f"binary_sensor.{DEVICE_1_NAME.lower()}_power")
    assert state.state == STATE_UNAVAILABLE


async def test_migrate_unique_ids(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that entities registered under the old bare device-ID unique_id are migrated."""
    config_entry.add_to_hass(hass)
    old_entry = entity_registry.async_get_or_create(
        BINARY_SENSOR_DOMAIN,
        DOMAIN,
        DEVICE_1_ID,
        config_entry=config_entry,
    )
    assert old_entry.unique_id == DEVICE_1_ID

    with patch("homeassistant.components.sense.PLATFORMS", [Platform.BINARY_SENSOR]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    migrated = entity_registry.async_get(old_entry.entity_id)
    assert migrated.unique_id == f"{MONITOR_ID}-{DEVICE_1_ID}"
