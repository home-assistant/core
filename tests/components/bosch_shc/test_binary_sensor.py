"""Tests for the Bosch SHC binary_sensor platform."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import patch

from boschshcpy import SHCBatteryDevice, SHCShutterContact
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    BinarySensorDeviceClass,
)
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import battery_only_device, setup_integration, shutter_contact_device

from tests.common import MockConfigEntry, snapshot_platform

OPEN = SHCShutterContact.ShutterContactService.State.OPEN
CLOSED = SHCShutterContact.ShutterContactService.State.CLOSED
BATTERY_OK = SHCBatteryDevice.BatteryLevelService.State.OK
BATTERY_LOW = SHCBatteryDevice.BatteryLevelService.State.LOW_BATTERY

CONTACT_ENTITY_ID = "binary_sensor.contact"
MOTION_BATTERY_ENTITY_ID = "binary_sensor.motion_battery"


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Restrict bosch_shc setup to the binary_sensor platform."""
    with patch(
        "homeassistant.components.bosch_shc.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        yield


@pytest.mark.parametrize(
    "device_buckets",
    [
        pytest.param(
            {
                "shutter_contacts": [shutter_contact_device()],
                "shutter_contacts2": [
                    shutter_contact_device(
                        device_id="hdm:HomeMaticIP:contact2", name="Contact 2"
                    )
                ],
                "motion_detectors": [battery_only_device()],
                "smoke_detectors": [
                    battery_only_device(
                        device_id="hdm:HomeMaticIP:smoke1", name="Smoke"
                    )
                ],
                "thermostats": [
                    battery_only_device(
                        device_id="hdm:HomeMaticIP:thermostat1", name="Thermostat"
                    )
                ],
                "twinguards": [
                    battery_only_device(
                        device_id="hdm:HomeMaticIP:twinguard1", name="Twinguard"
                    )
                ],
                "universal_switches": [
                    battery_only_device(
                        device_id="hdm:HomeMaticIP:universalswitch1",
                        name="Universal Switch",
                    )
                ],
                "wallthermostats": [
                    battery_only_device(
                        device_id="hdm:HomeMaticIP:wallthermostat1",
                        name="Wall Thermostat",
                    )
                ],
                "water_leakage_detectors": [
                    battery_only_device(
                        device_id="hdm:HomeMaticIP:waterleak1",
                        name="Water Leakage Detector",
                    )
                ],
            },
            id="entities",
        )
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Snapshot every binary_sensor entity the platform can create."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_session")
async def test_setup_no_devices_adds_nothing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """No devices in any bucket means no binary_sensor entities are created."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.async_all(BINARY_SENSOR_DOMAIN) == []


@pytest.mark.parametrize(
    ("device_buckets", "expected_ha_class"),
    [
        pytest.param(
            {
                "shutter_contacts": [
                    shutter_contact_device(device_class="ENTRANCE_DOOR")
                ]
            },
            BinarySensorDeviceClass.DOOR,
            id="entrance_door",
        ),
        pytest.param(
            {
                "shutter_contacts": [
                    shutter_contact_device(device_class="REGULAR_WINDOW")
                ]
            },
            BinarySensorDeviceClass.WINDOW,
            id="regular_window",
        ),
        pytest.param(
            {
                "shutter_contacts": [
                    shutter_contact_device(device_class="FRENCH_WINDOW")
                ]
            },
            BinarySensorDeviceClass.DOOR,
            id="french_window",
        ),
        pytest.param(
            {"shutter_contacts": [shutter_contact_device(device_class="GENERIC")]},
            BinarySensorDeviceClass.WINDOW,
            id="generic",
        ),
        pytest.param(
            {
                "shutter_contacts": [
                    shutter_contact_device(device_class="UNKNOWN_MODEL")
                ]
            },
            BinarySensorDeviceClass.WINDOW,
            id="unknown_defaults_to_window",
        ),
    ],
    indirect=["device_buckets"],
)
@pytest.mark.usefixtures("mock_session")
async def test_shutter_contact_device_class_mapping(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    expected_ha_class: BinarySensorDeviceClass,
) -> None:
    """The device_class switcher maps every known Bosch device_class, defaulting to window."""
    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(CONTACT_ENTITY_ID)) is not None
    assert state.attributes["device_class"] == expected_ha_class


@pytest.mark.parametrize(
    ("device_buckets", "expected_ha_state"),
    [
        pytest.param(
            {"shutter_contacts": [shutter_contact_device(state=OPEN)]},
            STATE_ON,
            id="open",
        ),
        pytest.param(
            {"shutter_contacts": [shutter_contact_device(state=CLOSED)]},
            STATE_OFF,
            id="closed",
        ),
    ],
    indirect=["device_buckets"],
)
@pytest.mark.usefixtures("mock_session")
async def test_shutter_contact_is_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    expected_ha_state: str,
) -> None:
    """The contact sensor is on exactly when the device reports OPEN."""
    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(CONTACT_ENTITY_ID)) is not None
    assert state.state == expected_ha_state


@pytest.mark.parametrize(
    ("device_buckets", "expected_ha_state"),
    [
        pytest.param(
            {"motion_detectors": [battery_only_device(batterylevel=BATTERY_OK)]},
            STATE_OFF,
            id="ok",
        ),
        pytest.param(
            {"motion_detectors": [battery_only_device(batterylevel=BATTERY_LOW)]},
            STATE_ON,
            id="low",
        ),
    ],
    indirect=["device_buckets"],
)
@pytest.mark.usefixtures("mock_session")
async def test_battery_sensor_is_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    expected_ha_state: str,
) -> None:
    """The battery sensor is on (problem) whenever the level isn't OK."""
    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(MOTION_BATTERY_ENTITY_ID)) is not None
    assert state.state == expected_ha_state
