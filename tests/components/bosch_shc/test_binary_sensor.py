"""Tests for the Bosch SHC binary_sensor platform."""

from unittest.mock import MagicMock

from boschshcpy import ShutterContactService, SurveillanceAlarmService
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.bosch_shc.binary_sensor import RETRY_DELAY
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .conftest import (
    setup_integration,
    shutter_contact_device,
    smoke_detection_system_device,
    twinguard_device,
)


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
