"""Tests for the sensor platform snapshot, and the sensors and device each baby has."""

from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import NOW, get_baby_device, setup_integration
from .factories import BABY_ONE_ID, BABY_TWO_ID, DEVICE_A, at, baby_payload
from .fake_server import FakeServer

KEYS = ("last_diaper", "last_feed", "last_sleep")
BABIES = ((BABY_ONE_ID, "baby_one", "Baby One"), (BABY_TWO_ID, "baby_two", "Baby Two"))


@pytest.fixture(autouse=True)
def _start_at_now(freezer: FrozenDateTimeFactory) -> None:
    """Freeze the clock at NOW before anything is set up.

    Timers scheduled at setup then share the clock the tests move, so moving it forward and
    ticking reaches them the way it does in core's tests.
    """
    freezer.move_to(NOW)


async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    populated_server: FakeServer,
) -> None:
    """Test the sensor entities and their states."""
    freezer.move_to(at(180))
    with patch("homeassistant.components.baby_tracker.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_each_baby_has_a_device_with_the_last_activity_sensors(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test each baby gets a device named after them, holding the sensors."""
    for baby_id, _, name in BABIES:
        device = get_baby_device(device_registry, baby_id)
        assert device is not None
        assert device.name == name
        sensors = er.async_entries_for_device(entity_registry, device.id)
        assert set(KEYS) <= {sensor.translation_key for sensor in sensors}


async def test_a_baby_without_a_name_gets_a_translated_device_name(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    server: FakeServer,
) -> None:
    """Test a baby with no name gets the device's translated name."""
    nameless_id = "44444444-DDDD-4DDD-8DDD-000000000004"
    server.add_payload(DEVICE_A, baby_payload("", nameless_id))
    await setup_integration(hass, mock_config_entry)

    device = get_baby_device(device_registry, nameless_id)
    assert device is not None
    assert device.name == "Baby"
    state = hass.states.get("sensor.baby_last_diaper")
    assert state is not None
    assert state.attributes["friendly_name"] == "Baby Last diaper"
