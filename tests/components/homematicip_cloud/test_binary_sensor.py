"""Tests for HomematicIP Cloud binary sensor."""

import json
from typing import Any
from unittest.mock import Mock, patch

from homematicip.base.enums import (
    BinaryBehaviorType,
    LockState,
    SmokeDetectorAlarmType,
    WindowState,
)
from homematicip.device import WaterSensor
import pytest
from pytest_homeassistant.common import (
    async_load_json_object_fixture,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.homematicip_cloud.binary_sensor import (
    ATTR_ACCELERATION_SENSOR_MODE,
    ATTR_ACCELERATION_SENSOR_NEUTRAL_POSITION,
    ATTR_ACCELERATION_SENSOR_SENSITIVITY,
    ATTR_ACCELERATION_SENSOR_TRIGGER_ANGLE,
    ATTR_MOISTURE_DETECTED,
    ATTR_MOTION_DETECTED,
    ATTR_POWER_MAINS_FAILURE,
    ATTR_PRESENCE_DETECTED,
    ATTR_WATER_LEVEL_DETECTED,
    ATTR_WINDOW_STATE,
)
from homeassistant.components.homematicip_cloud.const import DOMAIN
from homeassistant.components.homematicip_cloud.entity import (
    ATTR_EVENT_DELAY,
    ATTR_GROUP_MEMBER_UNREACHABLE,
    ATTR_LOW_BATTERY,
    ATTR_RSSI_DEVICE,
    ATTR_SABOTAGE,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .helper import (
    FIXTURE_DATA,
    HomeFactory,
    async_manipulate_test_data,
    get_and_check_entity_basics,
)


async def test_hmip_full_flush_lock_controller_binary_sensors(
    hass: HomeAssistant,
    default_mock_hap_factory: HomeFactory,
    full_flush_lock_controller_device_data: dict[str, Any],
) -> None:
    """Test HomematicIP full flush lock controller binary sensors."""
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Universal Motorschloss Controller"],
        extra_devices=[full_flush_lock_controller_device_data],
    )

    lock_entity_id = "binary_sensor.universal_motorschloss_controller_locked"
    lock_state, hmip_device = get_and_check_entity_basics(
        hass,
        mock_hap,
        lock_entity_id,
        "Universal Motorschloss Controller Locked",
        "HmIP-FLC",
    )
    # Per BinarySensorDeviceClass.LOCK convention, ON means unlocked / open
    # and OFF means locked / closed. Fixture initial state is LOCKED.
    assert lock_state.state == STATE_OFF

    glass_entity_id = "binary_sensor.universal_motorschloss_controller_glass_break"
    glass_state, _ = get_and_check_entity_basics(
        hass,
        mock_hap,
        glass_entity_id,
        "Universal Motorschloss Controller Glass break",
        "HmIP-FLC",
    )
    assert glass_state.state == STATE_ON
    assert (
        glass_state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.GLASS_BREAK
    )

    assert hmip_device is not None
    await async_manipulate_test_data(hass, hmip_device, "lockState", "UNLOCKED")
    lock_state = hass.states.get(lock_entity_id)
    assert lock_state
    assert lock_state.state == STATE_ON

    await async_manipulate_test_data(hass, hmip_device, "glassBroken", False)
    glass_state = hass.states.get(glass_entity_id)
    assert glass_state
    assert glass_state.state == STATE_OFF


@pytest.mark.parametrize(
    ("binary_behavior", "lock_state", "expected_state"),
    [
        # NORMALLY_OPEN: input ACTIVE (LOCKED) means contact closed = door
        # closed in HA semantics → off; idle (UNLOCKED) = door open → on.
        (BinaryBehaviorType.NORMALLY_OPEN, LockState.LOCKED, STATE_OFF),
        (BinaryBehaviorType.NORMALLY_OPEN, LockState.UNLOCKED, STATE_ON),
        # NORMALLY_CLOSE: polarity flipped — UNLOCKED reports the idle
        # state (door closed) and LOCKED reports input active (door open).
        (BinaryBehaviorType.NORMALLY_CLOSE, LockState.UNLOCKED, STATE_OFF),
        (BinaryBehaviorType.NORMALLY_CLOSE, LockState.LOCKED, STATE_ON),
    ],
)
async def test_hmip_full_flush_lock_controller_polarity(
    hass: HomeAssistant,
    default_mock_hap_factory: HomeFactory,
    full_flush_lock_controller_device_data: dict[str, Any],
    binary_behavior: BinaryBehaviorType,
    lock_state: LockState,
    expected_state: str,
) -> None:
    """Test FLC lock state respects binaryBehaviorType for both wirings."""
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Universal Motorschloss Controller"],
        extra_devices=[full_flush_lock_controller_device_data],
    )

    lock_entity_id = "binary_sensor.universal_motorschloss_controller_locked"
    _, hmip_device = get_and_check_entity_basics(
        hass,
        mock_hap,
        lock_entity_id,
        "Universal Motorschloss Controller Locked",
        "HmIP-FLC",
    )
    assert hmip_device is not None

    await async_manipulate_test_data(
        hass, hmip_device, "binaryBehaviorType", binary_behavior
    )
    await async_manipulate_test_data(hass, hmip_device, "lockState", lock_state.name)

    state = hass.states.get(lock_entity_id)
    assert state is not None
    assert state.state == expected_state


async def test_hmip_home_cloud_connection_sensor(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicipCloudConnectionSensor."""
    entity_id = "binary_sensor.home_cloud_connection"
    entity_name = "Home Cloud connection"
    device_model = None
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Cloud Connection"]
    )

    ha_state, _hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == STATE_ON

    await async_manipulate_test_data(hass, mock_hap.home, "connected", False)

    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_OFF


async def test_hmip_arming_blocked_sensor(
    hass: HomeAssistant,
    default_mock_hap_factory: HomeFactory,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the arming blocked sensor of the access point."""
    with patch(
        "homeassistant.components.homematicip_cloud.hap.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        mock_hap = await default_mock_hap_factory.async_get_mock_hap(
            test_devices=[], test_groups=[]
        )

    await snapshot_platform(
        hass, entity_registry, snapshot, mock_hap.config_entry.entry_id
    )


async def test_hmip_arming_blocked_sensor_follows_arming(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test the arming blocked sensor follows the replies of the alarm panel."""
    entity_id = "binary_sensor.home_arming_blocked"
    alarm_entity_id = "alarm_control_panel.hmip_alarm_control_panel"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_groups=["EXTERNAL", "INTERNAL"]
    )
    assert hass.states.get(entity_id).state == STATE_OFF

    home = mock_hap.home
    home.set_security_zones_activation_async.return_value = Mock(
        success=False,
        json={
            "channelActivationProblems": {"3014F7110000000000000005:1": ["WINDOW_OPEN"]}
        },
    )
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "alarm_control_panel",
            "alarm_arm_away",
            {"entity_id": alarm_entity_id},
            blocking=True,
        )
    assert hass.states.get(entity_id).state == STATE_ON

    home.set_security_zones_activation_async.return_value = Mock(success=False, json={})
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "alarm_control_panel",
            "alarm_arm_away",
            {"entity_id": alarm_entity_id},
            blocking=True,
        )
    assert hass.states.get(entity_id).state == STATE_ON

    home.set_security_zones_activation_async.return_value = Mock(success=True, json={})
    await hass.services.async_call(
        "alarm_control_panel",
        "alarm_disarm",
        {"entity_id": alarm_entity_id},
        blocking=True,
    )
    assert hass.states.get(entity_id).state == STATE_OFF


async def test_hmip_acceleration_sensor(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicipAccelerationSensor."""
    entity_id = "binary_sensor.garagentor_moving"
    entity_name = "Garagentor Moving"
    device_model = "HmIP-SAM"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Garagentor"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == STATE_ON
    assert ha_state.attributes[ATTR_ACCELERATION_SENSOR_MODE] == "FLAT_DECT"
    assert ha_state.attributes[ATTR_ACCELERATION_SENSOR_NEUTRAL_POSITION] == "VERTICAL"
    assert (
        ha_state.attributes[ATTR_ACCELERATION_SENSOR_SENSITIVITY] == "SENSOR_RANGE_4G"
    )
    assert ha_state.attributes[ATTR_ACCELERATION_SENSOR_TRIGGER_ANGLE] == 45
    service_call_counter = len(hmip_device.mock_calls)

    await async_manipulate_test_data(
        hass, hmip_device, "accelerationSensorTriggered", False
    )
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_OFF
    assert len(hmip_device.mock_calls) == service_call_counter + 1

    await async_manipulate_test_data(
        hass, hmip_device, "accelerationSensorTriggered", True
    )
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_ON
    assert len(hmip_device.mock_calls) == service_call_counter + 2


async def test_hmip_tilt_vibration_sensor(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicipTiltVibrationSensor."""
    entity_id = "binary_sensor.garage_neigungs_und_erschutterungssensor_moving"
    entity_name = "Garage Neigungs- und Erschütterungssensor Moving"
    device_model = "HmIP-STV"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Garage Neigungs- und Erschütterungssensor"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == STATE_ON
    assert ha_state.attributes[ATTR_ACCELERATION_SENSOR_MODE] == "FLAT_DECT"
    assert (
        ha_state.attributes[ATTR_ACCELERATION_SENSOR_SENSITIVITY] == "SENSOR_RANGE_2G"
    )
    assert ha_state.attributes[ATTR_ACCELERATION_SENSOR_TRIGGER_ANGLE] == 45
    service_call_counter = len(hmip_device.mock_calls)

    await async_manipulate_test_data(
        hass, hmip_device, "accelerationSensorTriggered", False
    )
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_OFF
    assert len(hmip_device.mock_calls) == service_call_counter + 1

    await async_manipulate_test_data(
        hass, hmip_device, "accelerationSensorTriggered", True
    )
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_ON
    assert len(hmip_device.mock_calls) == service_call_counter + 2


async def test_hmip_temperature_tilt_vibration_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    default_mock_hap_factory: HomeFactory,
) -> None:
    """Test the ELV-SH-TACO, whose tilt channel sits at index 2, not 1."""
    entity_id = "binary_sensor.wassertemperatursensor_moving"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Wassertemperatursensor"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, "Wassertemperatursensor Moving", "ELV-SH-TACO"
    )
    assert ha_state.state == STATE_ON

    entity = entity_registry.async_get(entity_id)
    assert entity.unique_id == "3014F711000000000000TACO_2_tilt_vibration"

    await async_manipulate_test_data(
        hass, hmip_device, "accelerationSensorTriggered", False
    )
    assert hass.states.get(entity_id).state == STATE_OFF


async def test_hmip_contact_interface(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicipContactInterface."""
    entity_id = "binary_sensor.kontakt_schnittstelle_unterputz_1_fach_opening"
    entity_name = "Kontakt-Schnittstelle Unterputz – 1-fach Opening"
    device_model = "HmIP-FCI1"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Kontakt-Schnittstelle Unterputz – 1-fach"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == STATE_OFF
    await async_manipulate_test_data(hass, hmip_device, "windowState", WindowState.OPEN)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_ON

    await async_manipulate_test_data(hass, hmip_device, "windowState", None)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_UNKNOWN


async def test_hmip_shutter_contact(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicipShutterContact."""
    entity_id = "binary_sensor.fenstergriffsensor_door"
    entity_name = "Fenstergriffsensor Door"
    device_model = "HmIP-SRH"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Fenstergriffsensor"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == STATE_ON
    assert ha_state.attributes[ATTR_WINDOW_STATE] == WindowState.TILTED

    await async_manipulate_test_data(hass, hmip_device, "windowState", WindowState.OPEN)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_ON
    assert ha_state.attributes[ATTR_WINDOW_STATE] == WindowState.OPEN

    await async_manipulate_test_data(
        hass, hmip_device, "windowState", WindowState.CLOSED
    )
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_OFF
    assert not ha_state.attributes.get(ATTR_WINDOW_STATE)

    await async_manipulate_test_data(hass, hmip_device, "windowState", None)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_UNKNOWN

    # test common attributes
    assert ha_state.attributes[ATTR_RSSI_DEVICE] == -54
    assert not ha_state.attributes.get(ATTR_SABOTAGE)
    await async_manipulate_test_data(hass, hmip_device, "sabotage", True)
    ha_state = hass.states.get(entity_id)
    assert ha_state.attributes[ATTR_SABOTAGE]


async def test_hmip_shutter_contact_optical(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicipShutterContact."""
    entity_id = "binary_sensor.sitzplatzture_door"
    entity_name = "Sitzplatzt\u00fcre Door"
    device_model = "HmIP-SWDO-PL"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Sitzplatzt\u00fcre"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == STATE_OFF
    await async_manipulate_test_data(hass, hmip_device, "windowState", WindowState.OPEN)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_ON

    await async_manipulate_test_data(hass, hmip_device, "windowState", None)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_UNKNOWN

    # test common attributes
    assert ha_state.attributes[ATTR_RSSI_DEVICE] == -72
    assert not ha_state.attributes.get(ATTR_SABOTAGE)
    await async_manipulate_test_data(hass, hmip_device, "sabotage", True)
    ha_state = hass.states.get(entity_id)
    assert ha_state.attributes[ATTR_SABOTAGE]


async def test_hmip_motion_detector(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicipMotionDetector."""
    entity_id = "binary_sensor.bewegungsmelder_fur_55er_rahmen_innen_motion"
    entity_name = "Bewegungsmelder für 55er Rahmen – innen Motion"
    device_model = "HmIP-SMI55"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Bewegungsmelder für 55er Rahmen – innen"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == STATE_OFF
    await async_manipulate_test_data(
        hass, hmip_device, "motionDetected", True, channel_real_index=3
    )
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_ON


async def test_hmip_presence_detector(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicipPresenceDetector."""
    entity_id = "binary_sensor.spi_1_presence"
    entity_name = "SPI_1 Presence"
    device_model = "HmIP-SPI"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(test_devices=["SPI_1"])

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == STATE_OFF
    await async_manipulate_test_data(hass, hmip_device, "presenceDetected", True)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_ON

    assert not ha_state.attributes.get(ATTR_EVENT_DELAY)
    await async_manipulate_test_data(hass, hmip_device, "eventDelay", True)
    ha_state = hass.states.get(entity_id)
    assert ha_state.attributes[ATTR_EVENT_DELAY]


async def test_hmip_pluggable_mains_failure_surveillance_sensor(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicipPresenceDetector."""
    entity_id = "binary_sensor.netzausfalluberwachung_power"
    entity_name = "Netzausfallüberwachung Power"
    device_model = "HmIP-PMFS"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Netzausfallüberwachung"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == STATE_ON
    await async_manipulate_test_data(hass, hmip_device, "powerMainsFailure", True)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_OFF


async def test_hmip_smoke_detector(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicipSmokeDetector."""
    entity_id = "binary_sensor.rauchwarnmelder_smoke"
    entity_name = "Rauchwarnmelder Smoke"
    device_model = "HmIP-SWSD"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Rauchwarnmelder"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == STATE_OFF
    await async_manipulate_test_data(
        hass,
        hmip_device,
        "smokeDetectorAlarmType",
        SmokeDetectorAlarmType.PRIMARY_ALARM,
    )
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_ON
    await async_manipulate_test_data(
        hass,
        hmip_device,
        "smokeDetectorAlarmType",
        None,
    )
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_OFF


async def test_hmip_smoke_detector_chamber_degraded(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicipSmokeDetectorChamberDegraded."""
    entity_id = "binary_sensor.rauchwarnmelder_chamber_degraded"
    entity_name = "Rauchwarnmelder Chamber degraded"
    device_model = "HmIP-SWSD"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Rauchwarnmelder"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == STATE_OFF
    await async_manipulate_test_data(hass, hmip_device, "chamberDegraded", True)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_ON


async def test_hmip_water_detector(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicipWaterDetector."""
    entity_id = "binary_sensor.wassersensor_moisture"
    entity_name = "Wassersensor Moisture"
    device_model = "HmIP-SWD"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Wassersensor"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == STATE_OFF
    await async_manipulate_test_data(hass, hmip_device, "waterlevelDetected", True)
    await async_manipulate_test_data(hass, hmip_device, "moistureDetected", False)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_ON

    await async_manipulate_test_data(hass, hmip_device, "waterlevelDetected", True)
    await async_manipulate_test_data(hass, hmip_device, "moistureDetected", True)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_ON

    await async_manipulate_test_data(hass, hmip_device, "waterlevelDetected", False)
    await async_manipulate_test_data(hass, hmip_device, "moistureDetected", True)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_ON

    await async_manipulate_test_data(hass, hmip_device, "waterlevelDetected", False)
    await async_manipulate_test_data(hass, hmip_device, "moistureDetected", False)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_OFF


async def test_hmip_storm_sensor(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicipStormSensor."""
    entity_id = "binary_sensor.weather_sensor_plus_storm"
    entity_name = "Weather Sensor – plus Storm"
    device_model = "HmIP-SWO-PL"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Weather Sensor – plus"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == STATE_OFF
    await async_manipulate_test_data(hass, hmip_device, "storm", True)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_ON


async def test_hmip_heating_output_sensor(
    hass: HomeAssistant,
    default_mock_hap_factory: HomeFactory,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the heating output of a wall thermostat."""
    entity_id = "binary_sensor.bwth_1_heating"
    with patch(
        "homeassistant.components.homematicip_cloud.hap.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        mock_hap = await default_mock_hap_factory.async_get_mock_hap(
            test_devices=["BWTH 1"], test_groups=[]
        )

    await snapshot_platform(
        hass, entity_registry, snapshot, mock_hap.config_entry.entry_id
    )

    hmip_device = mock_hap.hmip_device_by_entity_id[entity_id]
    await async_manipulate_test_data(
        hass, hmip_device, "valvePosition", 0.0, channel_real_index=2
    )
    assert hass.states.get(entity_id).state == STATE_OFF

    await async_manipulate_test_data(
        hass, hmip_device, "valvePosition", None, channel_real_index=2
    )
    assert hass.states.get(entity_id).state == STATE_UNKNOWN


async def test_hmip_heating_output_sensor_output_disabled(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test that a wall thermostat with its output disabled has no heating sensor."""
    fixture = await async_load_json_object_fixture(
        hass, "homematicip_cloud.json", DOMAIN
    )
    device = next(
        device for device in fixture["devices"].values() if device["label"] == "BWTH 1"
    )
    device["functionalChannels"]["2"]["internalSwitchOutputEnabled"] = False
    await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["BWTH 1"], extra_devices=[device]
    )

    assert hass.states.get("binary_sensor.bwth_1_heating") is None


async def test_hmip_motion_detector_switch_outdoor(
    hass: HomeAssistant,
    default_mock_hap_factory: HomeFactory,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the motion sensor of a motion detector with switching actuator."""
    entity_id = "binary_sensor.bewegungsmelder_haustur_motion"
    with patch(
        "homeassistant.components.homematicip_cloud.hap.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        mock_hap = await default_mock_hap_factory.async_get_mock_hap(
            test_devices=["Bewegungsmelder Haustür"], test_groups=[]
        )

    await snapshot_platform(
        hass, entity_registry, snapshot, mock_hap.config_entry.entry_id
    )

    hmip_device = mock_hap.hmip_device_by_entity_id[entity_id]
    await async_manipulate_test_data(
        hass, hmip_device, "motionDetected", True, channel=0, channel_real_index=1
    )
    assert hass.states.get(entity_id).state == STATE_ON


async def test_hmip_water_alarm_sensor(
    hass: HomeAssistant,
    default_mock_hap_factory: HomeFactory,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the water alarm of a water supply stop."""
    entity_id = "binary_sensor.wasserstopp_water_alarm"
    with patch(
        "homeassistant.components.homematicip_cloud.hap.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        mock_hap = await default_mock_hap_factory.async_get_mock_hap(
            test_devices=["Wasserstopp"], test_groups=[]
        )

    await snapshot_platform(
        hass, entity_registry, snapshot, mock_hap.config_entry.entry_id
    )

    hmip_device = mock_hap.hmip_device_by_entity_id[entity_id]
    await async_manipulate_test_data(hass, hmip_device, "waterAlarmActive", True)
    assert hass.states.get(entity_id).state == STATE_ON


async def test_hmip_rain_sensor(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicipRainSensor."""
    entity_id = "binary_sensor.wettersensor_pro_raining"
    entity_name = "Wettersensor - pro Raining"
    device_model = "HmIP-SWO-PR"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Wettersensor - pro"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == STATE_OFF
    await async_manipulate_test_data(hass, hmip_device, "raining", True)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_ON


async def test_hmip_sunshine_sensor(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicipSunshineSensor."""
    entity_id = "binary_sensor.wettersensor_pro_sunshine"
    entity_name = "Wettersensor - pro Sunshine"
    device_model = "HmIP-SWO-PR"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Wettersensor - pro"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == STATE_ON
    assert ha_state.attributes["today_sunshine_duration_in_minutes"] == 100
    await async_manipulate_test_data(hass, hmip_device, "sunshine", False)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_OFF


async def test_hmip_battery_sensor(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicipSunshineSensor."""
    entity_id = "binary_sensor.wohnungsture_battery"
    entity_name = "Wohnungstüre Battery"
    device_model = "HMIP-SWDO"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Wohnungstüre"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )
    assert [
        state.entity_id
        for state in hass.states.async_all("binary_sensor")
        if state.entity_id.startswith("binary_sensor.wohnungsture_battery")
    ] == [entity_id]

    assert ha_state.state == STATE_OFF
    await async_manipulate_test_data(hass, hmip_device, "lowBat", True)
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_ON


async def test_hmip_security_zone_sensor_group(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicipSecurityZoneSensorGroup."""
    entity_id = "binary_sensor.internal_securityzone"
    entity_name = "INTERNAL SecurityZone"
    device_model = "HmIP-SecurityZone"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_groups=["INTERNAL"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == STATE_OFF
    assert not ha_state.attributes.get(ATTR_MOTION_DETECTED)
    assert not ha_state.attributes.get(ATTR_PRESENCE_DETECTED)
    assert not ha_state.attributes.get(ATTR_GROUP_MEMBER_UNREACHABLE)
    assert not ha_state.attributes.get(ATTR_SABOTAGE)
    assert not ha_state.attributes.get(ATTR_WINDOW_STATE)

    await async_manipulate_test_data(hass, hmip_device, "motionDetected", True)
    await async_manipulate_test_data(hass, hmip_device, "presenceDetected", True)
    await async_manipulate_test_data(hass, hmip_device, "unreach", True)
    await async_manipulate_test_data(hass, hmip_device, "sabotage", True)
    await async_manipulate_test_data(hass, hmip_device, "windowState", WindowState.OPEN)
    ha_state = hass.states.get(entity_id)

    assert ha_state.state == STATE_ON
    assert ha_state.attributes[ATTR_MOTION_DETECTED]
    assert ha_state.attributes[ATTR_PRESENCE_DETECTED]
    assert ha_state.attributes[ATTR_GROUP_MEMBER_UNREACHABLE]
    assert ha_state.attributes[ATTR_SABOTAGE]
    assert ha_state.attributes[ATTR_WINDOW_STATE] == WindowState.OPEN


async def test_hmip_security_sensor_group(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicipSecuritySensorGroup."""
    entity_id = "binary_sensor.buro_sensors"
    entity_name = "Büro Sensors"
    device_model = None
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(test_groups=["Büro"])

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    await async_manipulate_test_data(
        hass,
        hmip_device,
        "smokeDetectorAlarmType",
        SmokeDetectorAlarmType.PRIMARY_ALARM,
    )
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_ON

    assert (
        ha_state.attributes["smoke_detector_alarm"]
        == SmokeDetectorAlarmType.PRIMARY_ALARM
    )
    await async_manipulate_test_data(
        hass, hmip_device, "smokeDetectorAlarmType", SmokeDetectorAlarmType.IDLE_OFF
    )
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_OFF

    assert not ha_state.attributes.get(ATTR_LOW_BATTERY)
    assert not ha_state.attributes.get(ATTR_MOTION_DETECTED)
    assert not ha_state.attributes.get(ATTR_PRESENCE_DETECTED)
    assert not ha_state.attributes.get(ATTR_POWER_MAINS_FAILURE)
    assert not ha_state.attributes.get(ATTR_MOISTURE_DETECTED)
    assert not ha_state.attributes.get(ATTR_WATER_LEVEL_DETECTED)
    assert not ha_state.attributes.get(ATTR_GROUP_MEMBER_UNREACHABLE)
    assert not ha_state.attributes.get(ATTR_SABOTAGE)
    assert not ha_state.attributes.get(ATTR_WINDOW_STATE)

    await async_manipulate_test_data(hass, hmip_device, "lowBat", True)
    await async_manipulate_test_data(hass, hmip_device, "motionDetected", True)
    await async_manipulate_test_data(hass, hmip_device, "presenceDetected", True)
    await async_manipulate_test_data(hass, hmip_device, "powerMainsFailure", True)
    await async_manipulate_test_data(hass, hmip_device, "moistureDetected", True)
    await async_manipulate_test_data(hass, hmip_device, "waterlevelDetected", True)
    await async_manipulate_test_data(hass, hmip_device, "unreach", True)
    await async_manipulate_test_data(hass, hmip_device, "sabotage", True)
    await async_manipulate_test_data(hass, hmip_device, "windowState", WindowState.OPEN)
    ha_state = hass.states.get(entity_id)

    assert ha_state.state == STATE_ON
    assert ha_state.attributes[ATTR_LOW_BATTERY]
    assert ha_state.attributes[ATTR_MOTION_DETECTED]
    assert ha_state.attributes[ATTR_PRESENCE_DETECTED]
    assert ha_state.attributes[ATTR_POWER_MAINS_FAILURE]
    assert ha_state.attributes[ATTR_MOISTURE_DETECTED]
    assert ha_state.attributes[ATTR_WATER_LEVEL_DETECTED]
    assert ha_state.attributes[ATTR_GROUP_MEMBER_UNREACHABLE]
    assert ha_state.attributes[ATTR_SABOTAGE]
    assert ha_state.attributes[ATTR_WINDOW_STATE] == WindowState.OPEN

    await async_manipulate_test_data(
        hass,
        hmip_device,
        "smokeDetectorAlarmType",
        SmokeDetectorAlarmType.INTRUSION_ALARM,
    )
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_ON


async def test_hmip_multi_contact_interface(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test HomematicipMultiContactInterface."""
    entity_id = "binary_sensor.wired_eingangsmodul_32_fach_channel10"
    entity_name = "Wired Eingangsmodul – 32-fach Channel10"
    device_model = "HmIPW-DRI32"
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Wired Eingangsmodul – 32-fach", "Licht Flur"]
    )

    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )

    assert ha_state.state == STATE_OFF
    await async_manipulate_test_data(
        hass, hmip_device, "windowState", WindowState.OPEN, channel_real_index=10
    )
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_ON

    await async_manipulate_test_data(
        hass, hmip_device, "windowState", None, channel_real_index=10
    )
    ha_state = hass.states.get(entity_id)
    assert ha_state.state == STATE_UNKNOWN

    # Test channel 32 of device
    entity_id = "binary_sensor.wired_eingangsmodul_32_fach_channel32"
    entity_name = "Wired Eingangsmodul – 32-fach Channel32"
    ha_state, hmip_device = get_and_check_entity_basics(
        hass, mock_hap, entity_id, entity_name, device_model
    )
    assert ha_state.state == STATE_OFF

    ha_state, hmip_device = get_and_check_entity_basics(
        hass,
        mock_hap,
        "binary_sensor.licht_flur_5",
        "Licht Flur 5",
        "HmIP-FCI6",
    )

    assert ha_state.state == STATE_UNKNOWN


async def test_hmip_binary_sensor_unknown_device_type(
    hass: HomeAssistant,
    default_mock_hap_factory: HomeFactory,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a device type the library does not know gets its water sensor."""
    device_data = json.loads(FIXTURE_DATA)["devices"]["3014F7110000000000000050"]
    device_data.update(
        id="3014F711000000000000UNKN", label="Unknown sensor", type="NEW_SENSOR"
    )
    mock_hap = await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Unknown sensor"], extra_devices=[device_data]
    )
    entity_id = "binary_sensor.unknown_sensor_moisture"
    hmip_device = mock_hap.hmip_device_by_entity_id[entity_id]
    assert not isinstance(hmip_device, WaterSensor)
    assert (
        entity_registry.async_get(entity_id).unique_id
        == "3014F711000000000000UNKN_1_water"
    )

    assert hass.states.get(entity_id).state == STATE_OFF
    await async_manipulate_test_data(
        hass, hmip_device, "moistureDetected", True, channel_real_index=1
    )
    assert hass.states.get(entity_id).state == STATE_ON


async def test_hmip_binary_sensor_second_channel(
    hass: HomeAssistant,
    default_mock_hap_factory: HomeFactory,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a second channel of the same type gets its own unique id."""
    device_data = json.loads(FIXTURE_DATA)["devices"]["3014F711000000000000BB11"]
    channel = dict(device_data["functionalChannels"]["1"], index=2)
    device_data["functionalChannels"]["2"] = channel
    device_data.update(id="3014F711000000000000TWO2", label="Two motion channels")
    await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Two motion channels"], extra_devices=[device_data]
    )

    assert sorted(
        entry.unique_id
        for entry in entity_registry.entities.values()
        if entry.unique_id.endswith("_motion")
    ) == ["3014F711000000000000TWO2_1_motion", "3014F711000000000000TWO2_2_motion"]


async def test_hmip_chamber_degraded_per_channel(
    hass: HomeAssistant,
    default_mock_hap_factory: HomeFactory,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the chamber sensor follows the channel that reports the field."""
    fixture = json.loads(FIXTURE_DATA)["devices"]
    device_data = fixture["3014F7110000000000000019"]
    device_data["functionalChannels"]["2"] = dict(
        fixture["3014F7110000000000000018"]["functionalChannels"]["1"], index=2
    )
    device_data.update(id="3014F711000000000000TWO2", label="Two smoke channels")
    await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Two smoke channels"], extra_devices=[device_data]
    )

    assert [
        entry.unique_id
        for entry in entity_registry.entities.values()
        if entry.unique_id.endswith("_chamber_degraded")
    ] == ["3014F711000000000000TWO2_1_chamber_degraded"]


async def test_hmip_smoke_detector_unknown_device_type(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test a smoke sensor without a known alarm type is unknown, not off."""
    device_data = json.loads(FIXTURE_DATA)["devices"]["3014F7110000000000000018"]
    device_data.update(
        id="3014F711000000000000UNKN", label="Unknown smoke", type="NEW_SMOKE"
    )
    await default_mock_hap_factory.async_get_mock_hap(
        test_devices=["Unknown smoke"], extra_devices=[device_data]
    )

    assert hass.states.get("binary_sensor.unknown_smoke_smoke").state == STATE_UNKNOWN


async def test_hmip_binary_sensor_unique_ids(
    hass: HomeAssistant,
    default_mock_hap_factory: HomeFactory,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that every binary sensor keeps its unique id."""
    await default_mock_hap_factory.async_get_mock_hap(
        test_devices=None, test_groups=None
    )

    assert {
        entry.entity_id: entry.unique_id
        for entry in entity_registry.entities.values()
        if entry.domain == "binary_sensor"
    } == {
        "binary_sensor.alarm_melder_battery": "3014F7110000000000000052_0_battery",
        "binary_sensor.alarmsirene_aussen_battery": "3014F7110000ABCDABCD0033_0_battery",
        "binary_sensor.alarmsirene_battery": "3014F7110000000000BBBBB8_0_battery",
        "binary_sensor.aussen_kuche_battery": "3014F71100000000000BBB17_0_battery",
        "binary_sensor.aussen_kuche_motion": "3014F71100000000000BBB17_1_motion",
        "binary_sensor.balkon_heizung_battery": "3014F7110000000000000017_0_battery",
        "binary_sensor.balkonfenster_battery": "3014F7110000000000000002_0_battery",
        "binary_sensor.balkonfenster_door": "3014F7110000000000000002_1_shutter_contact",
        "binary_sensor.balkonture_battery": "3014F7110000000000000000_0_battery",
        "binary_sensor.balkonture_door": "3014F7110000000000000000_1_shutter_contact",
        "binary_sensor.bewaesserungsaktor_battery": "3014F71100000000000SHWSM_0_battery",
        "binary_sensor.bewegungsmelder_fur_55er_rahmen_innen_battery": "3014F711000000000AAAAA25_0_battery",
        "binary_sensor.bewegungsmelder_fur_55er_rahmen_innen_motion": "3014F711000000000AAAAA25_1_motion",
        "binary_sensor.bewegungsmelder_haustur_motion": "3014F711000000000SMO230A_1_motion",
        "binary_sensor.buro_sensors": "00000000-0000-0000-0000-000000000009_security",
        "binary_sensor.bwth_1_heating": "3014F7110000000000000055_2_heating",
        "binary_sensor.dsdpcb_klingel_battery": "3014F7110000000000DSDPCB_0_battery",
        "binary_sensor.eingangsturkontakt_battery": "3014F7110000000000005551_0_battery",
        "binary_sensor.eingangsturkontakt_door": "3014F7110000000000005551_1_shutter_contact",
        "binary_sensor.elvshctv_battery": "3014F71100000000000SVCTH_0_battery",
        "binary_sensor.esi_gas_battery": "3014F7110000000000ESIGAS_0_battery",
        "binary_sensor.esi_iec2_battery": "3014F711000000000ESIIEC2_0_battery",
        "binary_sensor.esi_iec_battery": "3014F7110000000000ESIIEC_0_battery",
        "binary_sensor.esi_led_battery": "3014F7110000000000ESIIE3_0_battery",
        "binary_sensor.external_securityzone": "00000000-0000-0000-0000-000000000005_security_zone",
        "binary_sensor.fenster_battery": "3014F7110000000000000001_0_battery",
        "binary_sensor.fenster_battery_2": "3014F7110000000000000004_0_battery",
        "binary_sensor.fenster_door": "3014F7110000000000000001_1_shutter_contact",
        "binary_sensor.fenster_door_2": "3014F7110000000000000004_1_shutter_contact",
        "binary_sensor.fenstergriffsensor_battery": "3014F711AAAA000000000004_0_battery",
        "binary_sensor.fenstergriffsensor_door": "3014F711AAAA000000000004_1_shutter_contact",
        "binary_sensor.fernbedienung_8_tasten_battery": "3014F711BBBBBBBBBBBBB016_0_battery",
        "binary_sensor.garage_neigungs_und_erschutterungssensor_battery": "3014F7110TILTVIBRATIONSENSOR_0_battery",
        "binary_sensor.garage_neigungs_und_erschutterungssensor_moving": "3014F7110TILTVIBRATIONSENSOR_1_tilt_vibration",
        "binary_sensor.garagentor_battery": "3014F7110000000000000031_0_battery",
        "binary_sensor.garagentor_battery_2": "3014F7110000000000000WGC_0_battery",
        "binary_sensor.garagentor_moving": "3014F7110000000000000031_1_acceleration",
        "binary_sensor.haustuer_battery": "3014F7110000000000000DLD_0_battery",
        "binary_sensor.heizkorperthermostat2_battery": "3014F7110000000000000013_0_battery",
        "binary_sensor.heizkorperthermostat3_battery": "3014F7110000000000000016_0_battery",
        "binary_sensor.heizkorperthermostat4_battery": "3014F71100000000ETRV0013_0_battery",
        "binary_sensor.heizkorperthermostat_battery": "3014F7110000000000000012_0_battery",
        "binary_sensor.heizung_battery": "3014F7110000000000000011_0_battery",
        "binary_sensor.home_cloud_connection": "00000000-0000-0000-0000-000000000001_cloud_connection",
        "binary_sensor.internal_securityzone": "00000000-0000-0000-0000-000000000016_security_zone",
        "binary_sensor.kombisignalmelder_battery": "3014F7110000000000000MP3_0_battery",
        "binary_sensor.kontakt_schnittstelle_unterputz_1_fach_battery": "3014F7110000000000000029_0_battery",
        "binary_sensor.kontakt_schnittstelle_unterputz_1_fach_opening": "3014F7110000000000000029_1_contact",
        "binary_sensor.kuche_battery": "3014F7110000000000000003_0_battery",
        "binary_sensor.kuche_door": "3014F7110000000000000003_1_shutter_contact",
        "binary_sensor.kuche_heizung_battery": "3014F7110000000000000014_0_battery",
        "binary_sensor.licht_flur_1": "3014F7110000000000056775_1_contact",
        "binary_sensor.licht_flur_2": "3014F7110000000000056775_2_contact",
        "binary_sensor.licht_flur_4": "3014F7110000000000056775_4_contact",
        "binary_sensor.licht_flur_5": "3014F7110000000000056775_5_contact",
        "binary_sensor.licht_flur_6": "3014F7110000000000056775_6_contact",
        "binary_sensor.licht_flur_tur": "3014F7110000000000056775_3_contact",
        "binary_sensor.lichtsensor_nord_battery": "3014F711SLO0000000000026_0_battery",
        "binary_sensor.neigungssensor_tor_battery": "3014F7110000000000000CTV_0_battery",
        "binary_sensor.neigungssensor_tor_moving": "3014F7110000000000000CTV_1_tilt_vibration",
        "binary_sensor.netzausfalluberwachung_power": "3014F7110000000000ABCD50_1_mains_failure",
        "binary_sensor.rauchwarnmelder2_battery": "3014F7110000000000000019_0_battery",
        "binary_sensor.rauchwarnmelder2_smoke": "3014F7110000000000000019_1_smoke",
        "binary_sensor.rauchwarnmelder3_battery": "3014F7110000000000000020_0_battery",
        "binary_sensor.rauchwarnmelder3_smoke": "3014F7110000000000000020_1_smoke",
        "binary_sensor.rauchwarnmelder4_battery": "3014F7110000000000000021_0_battery",
        "binary_sensor.rauchwarnmelder4_smoke": "3014F7110000000000000021_1_smoke",
        "binary_sensor.rauchwarnmelder_battery": "3014F7110000000000000018_0_battery",
        "binary_sensor.rauchwarnmelder_chamber_degraded": "3014F7110000000000000018_1_chamber_degraded",
        "binary_sensor.rauchwarnmelder_smoke": "3014F7110000000000000018_1_smoke",
        "binary_sensor.raumbediengerat_analog_battery": "3014F711000000BBBB000005_0_battery",
        "binary_sensor.raumbediengerat_battery": "3014F711000BBBB000000000_0_battery",
        "binary_sensor.regensensor_raining": "3014F7110000RAIN_SENSOR_1_rain",
        "binary_sensor.schlafzimmer_sensors": "00000000-0000-0000-0000-000000000013_security",
        "binary_sensor.schliesser_magnet_battery": "3014F7110000000000000064_0_battery",
        "binary_sensor.schliesser_magnet_opening": "3014F7110000000000000064_1_contact",
        "binary_sensor.sitzplatzture_battery": "3014F7110SHUTTER_OPTICAL_0_battery",
        "binary_sensor.sitzplatzture_door": "3014F7110SHUTTER_OPTICAL_1_shutter_contact",
        "binary_sensor.soil_sensor_battery": "3014F7110000000000000SMS_0_battery",
        "binary_sensor.sonnenschutz_balkontur_battery": "3014F71100BLIND_MODULE00_0_battery",
        "binary_sensor.spdr_1_battery": "3014F7110000000000000054_0_battery",
        "binary_sensor.spi_1_battery": "3014F711AAAAAAAAAAAAAA51_0_battery",
        "binary_sensor.spi_1_presence": "3014F711AAAAAAAAAAAAAA51_1_presence",
        "binary_sensor.ste2_battery": "3014F7110000000000STE2015_0_battery",
        "binary_sensor.temperatur_und_luftfeuchtigkeitssensor_aussen_battery": "3014F711AAAA000000000002_0_battery",
        "binary_sensor.thermostat_evo_battery": "3014F7110000000000000E70_0_battery",
        "binary_sensor.thermostat_schlafen_tal_battery": "3014F711000000000000AAA5_0_battery",
        "binary_sensor.vorzimmer_battery": "3014F7110000000000000007_0_battery",
        "binary_sensor.vorzimmer_door": "3014F7110000000000000007_1_shutter_contact",
        "binary_sensor.vorzimmer_sensors": "00000000-0000-0000-0000-000000000015_security",
        "binary_sensor.wandtaster_6_fach_battery": "3014F711BBBBBBBBBBBBB017_0_battery",
        "binary_sensor.wandtaster_battery": "3014F711PUSH_BUTTON_FLAT_0_battery",
        "binary_sensor.wandthermostat2_battery": "3014F7110000000000000024_0_battery",
        "binary_sensor.wandthermostat3_battery": "3014F7110000000000000025_0_battery",
        "binary_sensor.wandthermostat4_battery": "3014F7110000000000000023_0_battery",
        "binary_sensor.wandthermostat_battery": "3014F7110000000000000022_0_battery",
        "binary_sensor.wassersensor_battery": "3014F7110000000000000050_0_battery",
        "binary_sensor.wassersensor_moisture": "3014F7110000000000000050_1_water",
        "binary_sensor.wasserstopp_battery": "3014F7110000000000000WSS_0_battery",
        "binary_sensor.wasserstopp_water_alarm": "3014F7110000000000000WSS_1_water_alarm",
        "binary_sensor.wassertemperatursensor_battery": "3014F711000000000000TACO_0_battery",
        "binary_sensor.wassertemperatursensor_moving": "3014F711000000000000TACO_2_tilt_vibration",
        "binary_sensor.weather_sensor_plus_battery": "3014F7110000000000000038_0_battery",
        "binary_sensor.weather_sensor_plus_raining": "3014F7110000000000000038_1_rain",
        "binary_sensor.weather_sensor_plus_storm": "3014F7110000000000000038_1_storm",
        "binary_sensor.weather_sensor_plus_sunshine": "3014F7110000000000000038_1_sunshine",
        "binary_sensor.wettersensor_battery": "3014F711AAAA000000000003_0_battery",
        "binary_sensor.wettersensor_pro_battery": "3014F711AAAA000000000001_0_battery",
        "binary_sensor.wettersensor_pro_raining": "3014F711AAAA000000000001_1_rain",
        "binary_sensor.wettersensor_pro_storm": "3014F711AAAA000000000001_1_storm",
        "binary_sensor.wettersensor_pro_sunshine": "3014F711AAAA000000000001_1_sunshine",
        "binary_sensor.wettersensor_storm": "3014F711AAAA000000000003_1_storm",
        "binary_sensor.wettersensor_sunshine": "3014F711AAAA000000000003_1_sunshine",
        "binary_sensor.wired_eingangsmodul_32_fach_channel1": "3014F711000WIREDINPUT32_1_contact",
        "binary_sensor.wired_eingangsmodul_32_fach_channel10": "3014F711000WIREDINPUT32_10_contact",
        "binary_sensor.wired_eingangsmodul_32_fach_channel11": "3014F711000WIREDINPUT32_11_contact",
        "binary_sensor.wired_eingangsmodul_32_fach_channel12": "3014F711000WIREDINPUT32_12_contact",
        "binary_sensor.wired_eingangsmodul_32_fach_channel13": "3014F711000WIREDINPUT32_13_contact",
        "binary_sensor.wired_eingangsmodul_32_fach_channel14": "3014F711000WIREDINPUT32_14_contact",
        "binary_sensor.wired_eingangsmodul_32_fach_channel15": "3014F711000WIREDINPUT32_15_contact",
        "binary_sensor.wired_eingangsmodul_32_fach_channel16": "3014F711000WIREDINPUT32_16_contact",
        "binary_sensor.wired_eingangsmodul_32_fach_channel17": "3014F711000WIREDINPUT32_17_contact",
        "binary_sensor.wired_eingangsmodul_32_fach_channel18": "3014F711000WIREDINPUT32_18_contact",
        "binary_sensor.wired_eingangsmodul_32_fach_channel19": "3014F711000WIREDINPUT32_19_contact",
        "binary_sensor.wired_eingangsmodul_32_fach_channel2": "3014F711000WIREDINPUT32_2_contact",
        "binary_sensor.wired_eingangsmodul_32_fach_channel20": "3014F711000WIREDINPUT32_20_contact",
        "binary_sensor.wired_eingangsmodul_32_fach_channel21": "3014F711000WIREDINPUT32_21_contact",
        "binary_sensor.wired_eingangsmodul_32_fach_channel22": "3014F711000WIREDINPUT32_22_contact",
        "binary_sensor.wired_eingangsmodul_32_fach_channel23": "3014F711000WIREDINPUT32_23_contact",
        "binary_sensor.wired_eingangsmodul_32_fach_channel24": "3014F711000WIREDINPUT32_24_contact",
        "binary_sensor.wired_eingangsmodul_32_fach_channel25": "3014F711000WIREDINPUT32_25_contact",
        "binary_sensor.wired_eingangsmodul_32_fach_channel26": "3014F711000WIREDINPUT32_26_contact",
        "binary_sensor.wired_eingangsmodul_32_fach_channel27": "3014F711000WIREDINPUT32_27_contact",
        "binary_sensor.wired_eingangsmodul_32_fach_channel28": "3014F711000WIREDINPUT32_28_contact",
        "binary_sensor.wired_eingangsmodul_32_fach_channel29": "3014F711000WIREDINPUT32_29_contact",
        "binary_sensor.wired_eingangsmodul_32_fach_channel3": "3014F711000WIREDINPUT32_3_contact",
        "binary_sensor.wired_eingangsmodul_32_fach_channel30": "3014F711000WIREDINPUT32_30_contact",
        "binary_sensor.wired_eingangsmodul_32_fach_channel31": "3014F711000WIREDINPUT32_31_contact",
        "binary_sensor.wired_eingangsmodul_32_fach_channel32": "3014F711000WIREDINPUT32_32_contact",
        "binary_sensor.wired_eingangsmodul_32_fach_channel4": "3014F711000WIREDINPUT32_4_contact",
        "binary_sensor.wired_eingangsmodul_32_fach_channel5": "3014F711000WIREDINPUT32_5_contact",
        "binary_sensor.wired_eingangsmodul_32_fach_channel6": "3014F711000WIREDINPUT32_6_contact",
        "binary_sensor.wired_eingangsmodul_32_fach_channel7": "3014F711000WIREDINPUT32_7_contact",
        "binary_sensor.wired_eingangsmodul_32_fach_channel8": "3014F711000WIREDINPUT32_8_contact",
        "binary_sensor.wired_eingangsmodul_32_fach_channel9": "3014F711000WIREDINPUT32_9_contact",
        "binary_sensor.wohnungsture_battery": "3014F7110000000000000006_0_battery",
        "binary_sensor.wohnungsture_door": "3014F7110000000000000006_1_shutter_contact",
        "binary_sensor.wohnzimmer_3_battery": "3014F71100000000ABCDEF10_0_battery",
        "binary_sensor.wohnzimmer_battery": "3014F711000000000000BB11_0_battery",
        "binary_sensor.wohnzimmer_battery_2": "3014F7110000000000000005_0_battery",
        "binary_sensor.wohnzimmer_door": "3014F7110000000000000005_1_shutter_contact",
        "binary_sensor.wohnzimmer_heizung_battery": "3014F7110000000000000015_0_battery",
        "binary_sensor.wohnzimmer_motion": "3014F711000000000000BB11_1_motion",
        "binary_sensor.wohnzimmer_sensors": "00000000-0000-0000-0000-000000000006_security",
        "binary_sensor.zisterne_battery": "3014F711000000000000DUSI_0_battery",
    }
