"""Tests for the Bosch SHC binary_sensor platform."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from boschshcpy import ShutterContactService, SurveillanceAlarmService
from boschshcpy.services_impl import OutdoorSirenPowerSupplyService
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.bosch_shc.binary_sensor import RETRY_DELAY
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import (
    climate_control_device,
    motion_detector2_device,
    outdoor_siren_device,
    setup_integration,
    shutter_contact_device,
    smoke_detection_system_device,
    twinguard_device,
)


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Restrict bosch_shc setup to the binary sensor platform."""
    with patch(
        "homeassistant.components.bosch_shc.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        yield


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "shutter_contacts": [
                shutter_contact_device(state=ShutterContactService.State.CLOSED)
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_shutter_contact_closed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A closed Shutter Contact is reported as off."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.shutter_contact")
    assert state is not None
    assert state.state == "off"


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "shutter_contacts": [
                shutter_contact_device(state=ShutterContactService.State.OPEN)
            ]
        }
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_shutter_contact_open(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """An open Shutter Contact is reported as on."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.shutter_contact")
    assert state is not None
    assert state.state == "on"


@pytest.mark.parametrize(
    "device_buckets",
    [{"shutter_contacts": [shutter_contact_device(device_class="ENTRANCE_DOOR")]}],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_shutter_contact_device_class(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A Shutter Contact's device_class maps to the binary_sensor device class."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.shutter_contact")
    assert state is not None
    assert state.attributes["device_class"] == "door"


TWINGUARD_ID = "hdm:HomeMaticIP:twinguard1"


def _smoke_buckets(
    alarm: SurveillanceAlarmService.State, triggered: set[str] | None = None
) -> dict:
    return {
        "twinguards": [twinguard_device()],
        "smoke_detection_system": smoke_detection_system_device(
            alarm=alarm, triggered=triggered
        ),
    }


def _fire_alarm_update(mock_session: MagicMock) -> None:
    system = mock_session.device_helper.smoke_detection_system
    next(iter(system.device_services[0].callbacks.values()))()


@pytest.mark.parametrize(
    "device_buckets",
    [_smoke_buckets(SurveillanceAlarmService.State.ALARM_OFF)],
    indirect=True,
)
async def test_twinguard_smoke_idle(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_session: MagicMock
) -> None:
    """No alarm: the sensor is off and the controller is not asked."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("binary_sensor.twinguard_smoke").state == STATE_OFF
    system = mock_session.device_helper.smoke_detection_system
    system.triggered_device_ids.assert_not_called()


@pytest.mark.parametrize(
    "device_buckets",
    [_smoke_buckets(SurveillanceAlarmService.State.ALARM_ON, {TWINGUARD_ID})],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_twinguard_smoke_triggered(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A Twinguard named as the alarm trigger is on."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("binary_sensor.twinguard_smoke").state == STATE_ON


@pytest.mark.parametrize(
    "device_buckets",
    [_smoke_buckets(SurveillanceAlarmService.State.ALARM_ON, {"hdm:other"})],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_twinguard_smoke_other_device(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """An alarm triggered by another device keeps this sensor off."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("binary_sensor.twinguard_smoke").state == STATE_OFF


@pytest.mark.parametrize(
    "device_buckets",
    [_smoke_buckets(SurveillanceAlarmService.State.ALARM_ON, {TWINGUARD_ID})],
    indirect=True,
)
async def test_twinguard_smoke_clears_and_unsubscribes(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_session: MagicMock
) -> None:
    """Alarm off clears the sensor; unloading removes the callback."""
    await setup_integration(hass, mock_config_entry)
    system = mock_session.device_helper.smoke_detection_system
    service = system.device_services[0]
    assert hass.states.get("binary_sensor.twinguard_smoke").state == STATE_ON

    system.alarm = SurveillanceAlarmService.State.ALARM_OFF
    _fire_alarm_update(mock_session)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.twinguard_smoke").state == STATE_OFF

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert not service.callbacks


@pytest.mark.parametrize(
    "device_buckets",
    [_smoke_buckets(SurveillanceAlarmService.State.ALARM_ON)],
    indirect=True,
)
async def test_twinguard_smoke_fetch_fails_then_retries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A failing lookup makes the sensor unavailable and is retried."""
    system = mock_session.device_helper.smoke_detection_system
    system.triggered_device_ids.side_effect = OSError("boom")
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get("binary_sensor.twinguard_smoke").state == STATE_UNAVAILABLE

    system.triggered_device_ids.side_effect = None
    system.triggered_device_ids.return_value = {TWINGUARD_ID}
    freezer.tick(RETRY_DELAY + 1)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.twinguard_smoke").state == STATE_ON


@pytest.mark.parametrize(
    "device_buckets",
    [
        {
            "twinguards": [
                twinguard_device(),
                twinguard_device(device_id="hdm:HomeMaticIP:twinguard2", name="Second"),
            ],
            "smoke_detection_system": smoke_detection_system_device(
                alarm=SurveillanceAlarmService.State.ALARM_ON,
                triggered={"hdm:HomeMaticIP:twinguard2"},
            ),
        }
    ],
    indirect=True,
)
async def test_twinguard_smoke_looks_up_once(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_session: MagicMock
) -> None:
    """All Twinguards share a single lookup per alarm update."""
    await setup_integration(hass, mock_config_entry)

    system = mock_session.device_helper.smoke_detection_system
    assert system.triggered_device_ids.call_count == 1
    assert hass.states.get("binary_sensor.twinguard_smoke").state == STATE_OFF
    assert hass.states.get("binary_sensor.second_smoke").state == STATE_ON


@pytest.mark.parametrize(
    ("device_kwargs", "entity_id", "expected"),
    [
        ({"has_demand": True}, "binary_sensor.living_room_call_for_heat", STATE_ON),
        ({}, "binary_sensor.living_room_call_for_heat", STATE_OFF),
        (
            {"has_demand": True, "supports_cooling": True, "cooling_mode": True},
            "binary_sensor.living_room_call_for_heat",
            STATE_OFF,
        ),
        (
            {"setpoint_temperature_offset_active": True},
            "binary_sensor.living_room_schedule_override_active",
            STATE_ON,
        ),
        ({"summer_mode": True}, "binary_sensor.living_room_heating_break", STATE_ON),
        (
            {"ventilation_mode": True},
            "binary_sensor.living_room_sustainable_ventilation",
            STATE_ON,
        ),
    ],
)
@pytest.mark.usefixtures("mock_session")
async def test_climate_control_binary_sensors(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    device_kwargs: dict[str, bool],
    entity_id: str,
    expected: str,
) -> None:
    """A room climate control exposes its demand and mode flags."""
    mock_session.device_helper.climate_controls = [
        climate_control_device(**device_kwargs)
    ]
    mock_session.room.return_value.name = "Living Room"
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected
    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    device = device_registry.async_get(entry.device_id)
    assert device is not None
    assert device.name == "Living Room"


@pytest.mark.parametrize(
    ("device_kwargs", "entity_id", "expected"),
    [
        (
            {"acoustic_alarm_on": True},
            "binary_sensor.outdoor_siren_acoustic_alarm",
            STATE_ON,
        ),
        ({}, "binary_sensor.outdoor_siren_acoustic_alarm", STATE_OFF),
        (
            {"visual_alarm_on": True},
            "binary_sensor.outdoor_siren_visual_alarm",
            STATE_ON,
        ),
        ({"tamper_activated": True}, "binary_sensor.outdoor_siren_tamper", STATE_ON),
        ({}, "binary_sensor.outdoor_siren_tamper", STATE_OFF),
    ],
)
@pytest.mark.usefixtures("mock_session")
async def test_outdoor_siren_binary_sensors(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_kwargs: dict[str, bool],
    entity_id: str,
    expected: str,
) -> None:
    """An outdoor siren exposes its alarm and tamper state."""
    mock_session.device_helper.outdoor_sirens = [outdoor_siren_device(**device_kwargs)]
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected


@pytest.mark.usefixtures("mock_session")
async def test_outdoor_siren_no_siren_service(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """An outdoor siren without the siren service gets no alarm sensors."""
    siren = outdoor_siren_device()
    siren.siren = None
    mock_session.device_helper.outdoor_sirens = [siren]
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("binary_sensor.outdoor_siren_acoustic_alarm") is None
    assert hass.states.get("binary_sensor.outdoor_siren_visual_alarm") is None
    assert hass.states.get("binary_sensor.outdoor_siren_tamper") is None


@pytest.mark.parametrize(
    ("device_kwargs", "entity_id", "expected"),
    [
        ({"occupied": True}, "binary_sensor.motion_detector_occupancy", STATE_ON),
        ({}, "binary_sensor.motion_detector_occupancy", STATE_OFF),
        ({"was_tampered": True}, "binary_sensor.motion_detector_tamper", STATE_ON),
        ({}, "binary_sensor.motion_detector_tamper", STATE_OFF),
    ],
)
@pytest.mark.usefixtures("mock_session")
async def test_motion_detector2_binary_sensors(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_kwargs: dict[str, bool],
    entity_id: str,
    expected: str,
) -> None:
    """A Motion Detector II exposes occupancy and tamper state."""
    mock_session.device_helper.motion_detectors2 = [
        motion_detector2_device(**device_kwargs)
    ]
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected


SMOKE_ALARM_ENTITY_ID = "binary_sensor.smoke_detection_system_smoke"


@pytest.mark.parametrize(
    ("alarm", "expected"),
    [
        (SurveillanceAlarmService.State.ALARM_OFF, STATE_OFF),
        (SurveillanceAlarmService.State.PRE_ALARM, STATE_ON),
        (SurveillanceAlarmService.State.ALARM_ON, STATE_ON),
        (SurveillanceAlarmService.State.ALARM_MUTED, STATE_ON),
    ],
)
async def test_smoke_detection_system_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
    alarm: SurveillanceAlarmService.State,
    expected: str,
) -> None:
    """The system sensor is on for every alarm state except off."""
    mock_session.device_helper.smoke_detection_system = smoke_detection_system_device(
        alarm=alarm
    )
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(SMOKE_ALARM_ENTITY_ID)
    assert state is not None
    assert state.state == expected


@pytest.mark.parametrize(
    ("attribute", "entity_id"),
    [
        ("ac_dc_error", "binary_sensor.outdoor_siren_ac_dc_error"),
        ("battery_defect", "binary_sensor.outdoor_siren_battery_defect"),
        (
            "battery_temperature_abnormal",
            "binary_sensor.outdoor_siren_battery_temperature_abnormal",
        ),
        (
            "primary_power_supply_outage",
            "binary_sensor.outdoor_siren_primary_power_supply_outage",
        ),
    ],
)
@pytest.mark.parametrize(("value", "expected"), [(True, STATE_ON), (False, STATE_OFF)])
@pytest.mark.usefixtures("mock_session")
async def test_outdoor_siren_power_supply_binary_sensors(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
    attribute: str,
    entity_id: str,
    value: bool,
    expected: str,
) -> None:
    """An outdoor siren exposes its power-supply fault flags."""
    power_supply = MagicMock(spec=OutdoorSirenPowerSupplyService)
    power_supply.ac_dc_error = False
    power_supply.battery_defect = False
    power_supply.battery_temperature_abnormal = False
    power_supply.primary_power_supply_outage = False
    setattr(power_supply, attribute, value)
    mock_session.device_helper.outdoor_sirens = [
        outdoor_siren_device(power_supply=power_supply)
    ]
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected


async def test_smoke_detection_system_push_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
) -> None:
    """A pushed alarm change updates the sensor."""
    system = smoke_detection_system_device(
        alarm=SurveillanceAlarmService.State.ALARM_OFF
    )
    mock_session.device_helper.smoke_detection_system = system
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(SMOKE_ALARM_ENTITY_ID).state == STATE_OFF

    system.alarm = SurveillanceAlarmService.State.ALARM_ON
    _fire_alarm_update(mock_session)
    await hass.async_block_till_done()

    assert hass.states.get(SMOKE_ALARM_ENTITY_ID).state == STATE_ON


@pytest.mark.usefixtures("mock_session")
async def test_outdoor_siren_without_power_supply(
    hass: HomeAssistant,
    mock_session: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """An outdoor siren without the power-supply service gets no fault sensors."""
    mock_session.device_helper.outdoor_sirens = [outdoor_siren_device()]
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("binary_sensor.outdoor_siren_ac_dc_error") is None
    assert hass.states.get("binary_sensor.outdoor_siren_battery_defect") is None
