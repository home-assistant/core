"""Tests for the Bosch SHC binary_sensor platform."""

from __future__ import annotations

from unittest.mock import create_autospec

from boschshcpy import SHCBatteryDevice, SHCShutterContact
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import setup_integration

from tests.common import snapshot_platform

OPEN = SHCShutterContact.ShutterContactService.State.OPEN
CLOSED = SHCShutterContact.ShutterContactService.State.CLOSED
BATTERY_OK = SHCBatteryDevice.BatteryLevelService.State.OK
BATTERY_LOW = SHCBatteryDevice.BatteryLevelService.State.LOW_BATTERY

CONTACT_ENTITY_ID = "binary_sensor.contact"
MOTION_BATTERY_ENTITY_ID = "binary_sensor.motion_battery"


def _shutter_contact_device(
    device_id: str = "hdm:HomeMaticIP:contact1",
    name: str = "Contact",
    device_class: str = "ENTRANCE_DOOR",
    state: SHCShutterContact.ShutterContactService.State = CLOSED,
    batterylevel: SHCBatteryDevice.BatteryLevelService.State = BATTERY_OK,
) -> SHCShutterContact:
    """Build a minimal shutter-contact device double."""
    device = create_autospec(SHCShutterContact, instance=True, spec_set=True)
    device.name = name
    device.id = device_id
    device.root_device_id = "test-mac"
    device.serial = f"serial-{device_id}"
    device.device_class = device_class
    device.state = state
    device.batterylevel = batterylevel
    device.device_services = []
    device.manufacturer = "Bosch"
    device.device_model = "SWD"
    device.status = "AVAILABLE"
    device.deleted = False
    return device


def _battery_only_device(
    device_id: str = "hdm:HomeMaticIP:motion1",
    name: str = "Motion",
    batterylevel: SHCBatteryDevice.BatteryLevelService.State = BATTERY_OK,
) -> SHCBatteryDevice:
    """Build a minimal device double for a battery-only bucket (e.g. motion_detectors)."""
    device = create_autospec(SHCBatteryDevice, instance=True, spec_set=True)
    device.name = name
    device.id = device_id
    device.root_device_id = "test-mac"
    device.serial = f"serial-{device_id}"
    device.batterylevel = batterylevel
    device.device_services = []
    device.manufacturer = "Bosch"
    device.device_model = "MD"
    device.status = "AVAILABLE"
    device.deleted = False
    return device


async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot every binary_sensor entity the platform can create."""
    entry = await setup_integration(
        hass,
        [Platform.BINARY_SENSOR],
        shutter_contacts=[_shutter_contact_device()],
        shutter_contacts2=[
            _shutter_contact_device(
                device_id="hdm:HomeMaticIP:contact2", name="Contact 2"
            )
        ],
        motion_detectors=[_battery_only_device()],
        smoke_detectors=[
            _battery_only_device(device_id="hdm:HomeMaticIP:smoke1", name="Smoke")
        ],
        thermostats=[
            _battery_only_device(
                device_id="hdm:HomeMaticIP:thermostat1", name="Thermostat"
            )
        ],
        twinguards=[
            _battery_only_device(
                device_id="hdm:HomeMaticIP:twinguard1", name="Twinguard"
            )
        ],
        universal_switches=[
            _battery_only_device(
                device_id="hdm:HomeMaticIP:universalswitch1", name="Universal Switch"
            )
        ],
        wallthermostats=[
            _battery_only_device(
                device_id="hdm:HomeMaticIP:wallthermostat1", name="Wall Thermostat"
            )
        ],
        water_leakage_detectors=[
            _battery_only_device(
                device_id="hdm:HomeMaticIP:waterleak1", name="Water Leakage Detector"
            )
        ],
    )

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_setup_no_devices_adds_nothing(hass: HomeAssistant) -> None:
    """No devices in any bucket means no binary_sensor entities are created."""
    await setup_integration(hass, [Platform.BINARY_SENSOR])

    assert hass.states.async_all(BINARY_SENSOR_DOMAIN) == []


@pytest.mark.parametrize(
    ("device_class", "expected_ha_class"),
    [
        pytest.param("ENTRANCE_DOOR", "door", id="entrance_door"),
        pytest.param("REGULAR_WINDOW", "window", id="regular_window"),
        pytest.param("FRENCH_WINDOW", "door", id="french_window"),
        pytest.param("GENERIC", "window", id="generic"),
        pytest.param("UNKNOWN_MODEL", "window", id="unknown_defaults_to_window"),
    ],
)
async def test_shutter_contact_device_class_mapping(
    hass: HomeAssistant, device_class: str, expected_ha_class: str
) -> None:
    """The device_class switcher maps every known Bosch device_class, defaulting to window."""
    device = _shutter_contact_device(device_class=device_class)
    await setup_integration(hass, [Platform.BINARY_SENSOR], shutter_contacts=[device])

    assert hass.states.get(CONTACT_ENTITY_ID).attributes["device_class"] == (
        expected_ha_class
    )


@pytest.mark.parametrize(
    ("contact_state", "expected_ha_state"),
    [
        pytest.param(OPEN, STATE_ON, id="open"),
        pytest.param(CLOSED, STATE_OFF, id="closed"),
    ],
)
async def test_shutter_contact_is_on(
    hass: HomeAssistant,
    contact_state: SHCShutterContact.ShutterContactService.State,
    expected_ha_state: str,
) -> None:
    """The contact sensor is on exactly when the device reports OPEN."""
    device = _shutter_contact_device(state=contact_state)
    await setup_integration(hass, [Platform.BINARY_SENSOR], shutter_contacts=[device])

    assert hass.states.get(CONTACT_ENTITY_ID).state == expected_ha_state


@pytest.mark.parametrize(
    ("batterylevel", "expected_ha_state"),
    [
        pytest.param(BATTERY_OK, STATE_OFF, id="ok"),
        pytest.param(BATTERY_LOW, STATE_ON, id="low"),
    ],
)
async def test_battery_sensor_is_on(
    hass: HomeAssistant,
    batterylevel: SHCBatteryDevice.BatteryLevelService.State,
    expected_ha_state: str,
) -> None:
    """The battery sensor is on (problem) whenever the level isn't OK."""
    device = _battery_only_device(batterylevel=batterylevel)
    await setup_integration(hass, [Platform.BINARY_SENSOR], motion_detectors=[device])

    assert hass.states.get(MOTION_BATTERY_ENTITY_ID).state == expected_ha_state
