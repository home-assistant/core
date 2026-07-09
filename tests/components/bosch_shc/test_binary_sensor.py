"""Tests for the Bosch SHC binary_sensor platform."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

from boschshcpy import SHCBatteryDevice, SHCShutterContact
import pytest

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.bosch_shc.const import (
    CONF_SSL_CERTIFICATE,
    CONF_SSL_KEY,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

OPEN = SHCShutterContact.ShutterContactService.State.OPEN
CLOSED = SHCShutterContact.ShutterContactService.State.CLOSED
BATTERY_OK = SHCBatteryDevice.BatteryLevelService.State.OK
BATTERY_LOW = SHCBatteryDevice.BatteryLevelService.State.LOW_BATTERY

# Every device_helper bucket bosch_shc's platforms iterate over, defaulted to
# empty so a full component setup only ever creates the binary_sensor
# entities under test here, regardless of what other platforms look for.
_EMPTY_DEVICE_BUCKETS: dict[str, list[Any]] = {
    bucket: []
    for bucket in (
        "shutter_controls",
        "thermostats",
        "wallthermostats",
        "twinguards",
        "smart_plugs",
        "light_switches_bsm",
        "smart_plugs_compact",
        "shutter_contacts",
        "shutter_contacts2",
        "motion_detectors",
        "smoke_detectors",
        "universal_switches",
        "water_leakage_detectors",
        "camera_eyes",
        "camera_360",
    )
}


def _shutter_contact_device(
    device_id: str = "hdm:HomeMaticIP:contact1",
    device_class: str = "ENTRANCE_DOOR",
    state: SHCShutterContact.ShutterContactService.State = CLOSED,
    batterylevel: SHCBatteryDevice.BatteryLevelService.State = BATTERY_OK,
) -> SimpleNamespace:
    """Build a minimal shutter-contact device double."""
    return SimpleNamespace(
        name="Test Contact",
        id=device_id,
        root_device_id="test-mac",
        serial=f"serial-{device_id}",
        device_class=device_class,
        state=state,
        batterylevel=batterylevel,
        device_services=[],
        manufacturer="Bosch",
        device_model="SWD",
        status="AVAILABLE",
        deleted=False,
        subscribe_callback=MagicMock(),
        unsubscribe_callback=MagicMock(),
    )


def _battery_only_device(
    device_id: str = "hdm:HomeMaticIP:motion1",
    batterylevel: SHCBatteryDevice.BatteryLevelService.State = BATTERY_OK,
) -> SimpleNamespace:
    """Build a minimal device double for a battery-only bucket (e.g. motion_detectors)."""
    return SimpleNamespace(
        name="Test Motion",
        id=device_id,
        root_device_id="test-mac",
        serial=f"serial-{device_id}",
        batterylevel=batterylevel,
        device_services=[],
        manufacturer="Bosch",
        device_model="MD",
        status="AVAILABLE",
        deleted=False,
        subscribe_callback=MagicMock(),
        unsubscribe_callback=MagicMock(),
    )


async def _setup_binary_sensor_integration(
    hass: HomeAssistant, **device_buckets: list[SimpleNamespace]
) -> MockConfigEntry:
    """Set up bosch_shc with the given device_helper buckets, via a mocked session."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_SSL_CERTIFICATE: "cert",
            CONF_SSL_KEY: "key",
        },
        unique_id="test-mac",
    )
    entry.add_to_hass(hass)

    mock_session = MagicMock()
    mock_session.information.unique_id = "test-mac"
    mock_session.information.updateState.name = "UP_TO_DATE"
    mock_session.information.version = "2.0"
    mock_session.device_helper = SimpleNamespace(
        **{**_EMPTY_DEVICE_BUCKETS, **device_buckets}
    )

    with patch(
        "homeassistant.components.bosch_shc.SHCSession", return_value=mock_session
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


async def test_shutter_contact_creates_contact_and_battery_sensors(
    hass: HomeAssistant,
) -> None:
    """A shutter_contacts device yields both a contact sensor and a battery sensor."""
    device = _shutter_contact_device()
    await _setup_binary_sensor_integration(hass, shutter_contacts=[device])

    states = hass.states.async_all(BINARY_SENSOR_DOMAIN)
    assert len(states) == 2

    contact_state = hass.states.get("binary_sensor.test_contact")
    assert contact_state is not None
    assert contact_state.attributes["device_class"] == "door"

    battery_state = hass.states.get("binary_sensor.test_contact_battery")
    assert battery_state is not None
    assert battery_state.attributes["device_class"] == "battery"


async def test_shutter_contacts2_creates_contact_and_battery_sensors(
    hass: HomeAssistant,
) -> None:
    """A shutter_contacts2 device also yields both a contact and a battery sensor."""
    device = _shutter_contact_device(device_id="hdm:HomeMaticIP:contact2")
    await _setup_binary_sensor_integration(hass, shutter_contacts2=[device])

    assert len(hass.states.async_all(BINARY_SENSOR_DOMAIN)) == 2


async def test_battery_only_bucket_creates_no_contact_sensor(
    hass: HomeAssistant,
) -> None:
    """A device in a battery-only bucket yields a battery sensor but no contact sensor."""
    device = _battery_only_device()
    await _setup_binary_sensor_integration(hass, motion_detectors=[device])

    states = hass.states.async_all(BINARY_SENSOR_DOMAIN)
    assert len(states) == 1
    assert states[0].attributes["device_class"] == "battery"


async def test_setup_no_devices_adds_nothing(hass: HomeAssistant) -> None:
    """No devices in any bucket means no binary_sensor entities are created."""
    await _setup_binary_sensor_integration(hass)

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
    await _setup_binary_sensor_integration(hass, shutter_contacts=[device])

    state = hass.states.get("binary_sensor.test_contact")
    assert state is not None
    assert state.attributes["device_class"] == expected_ha_class


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
    await _setup_binary_sensor_integration(hass, shutter_contacts=[device])

    state = hass.states.get("binary_sensor.test_contact")
    assert state is not None
    assert state.state == expected_ha_state


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
    await _setup_binary_sensor_integration(hass, motion_detectors=[device])

    state = hass.states.get("binary_sensor.test_motion_battery")
    assert state is not None
    assert state.state == expected_ha_state
