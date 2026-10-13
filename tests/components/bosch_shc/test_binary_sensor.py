"""Tests for the Bosch SHC binary_sensor platform."""

import json
from unittest.mock import MagicMock

from boschshcpy import ShutterContactService, SurveillanceAlarmService
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.const import STATE_OFF, STATE_ON
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


def _smoke_message(trigger_id: str, event_type: str = "ALARM_ON") -> dict:
    return {
        "messageCode": {"name": "SMOKE_ALARM"},
        "sourceId": "hdm:ZigBee:smokedetectionsystem",
        "arguments": {
            "surveillanceEvents": [{"type": event_type, "triggerId": trigger_id}]
        },
    }


def _smoke_buckets(alarm: SurveillanceAlarmService.State) -> dict:
    return {
        "twinguards": [twinguard_device()],
        "smoke_detection_system": smoke_detection_system_device(alarm=alarm),
    }


@pytest.mark.parametrize(
    "device_buckets",
    [_smoke_buckets(SurveillanceAlarmService.State.ALARM_OFF)],
    indirect=True,
)
@pytest.mark.usefixtures("mock_session")
async def test_twinguard_smoke_idle(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """No alarm: the sensor is off and no messages are fetched."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("binary_sensor.twinguard_smoke").state == STATE_OFF


@pytest.mark.parametrize(
    "device_buckets",
    [_smoke_buckets(SurveillanceAlarmService.State.ALARM_ON)],
    indirect=True,
)
async def test_twinguard_smoke_alarm_from_message(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_session: MagicMock
) -> None:
    """An alarm message naming this Twinguard turns the sensor on."""
    mock_session.api.get_messages.return_value = [
        _smoke_message("hdm:HomeMaticIP:twinguard1")
    ]
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("binary_sensor.twinguard_smoke").state == STATE_ON


@pytest.mark.parametrize(
    "device_buckets",
    [_smoke_buckets(SurveillanceAlarmService.State.ALARM_ON)],
    indirect=True,
)
async def test_twinguard_smoke_other_device(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_session: MagicMock
) -> None:
    """An alarm triggered by another device keeps this sensor off."""
    mock_session.api.get_messages.return_value = [_smoke_message("hdm:other")]
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("binary_sensor.twinguard_smoke").state == STATE_OFF


@pytest.mark.parametrize(
    "device_buckets",
    [_smoke_buckets(SurveillanceAlarmService.State.ALARM_ON)],
    indirect=True,
)
async def test_twinguard_smoke_ended_alarm_and_string_events(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_session: MagicMock
) -> None:
    """ALARM_OFF messages are ignored, JSON string events are parsed."""
    ended = _smoke_message("hdm:HomeMaticIP:twinguard1", "ALARM_OFF")
    mock_session.api.get_messages.return_value = [ended]
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get("binary_sensor.twinguard_smoke").state == STATE_OFF

    as_string = _smoke_message("hdm:HomeMaticIP:twinguard1")
    as_string["arguments"]["surveillanceEvents"] = json.dumps(
        as_string["arguments"]["surveillanceEvents"]
    )
    mock_session.api.get_messages.return_value = [as_string]
    service = mock_session.device_helper.smoke_detection_system.device_services[0]
    next(iter(service.callbacks.values()))()
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.twinguard_smoke").state == STATE_ON


@pytest.mark.parametrize(
    "device_buckets",
    [_smoke_buckets(SurveillanceAlarmService.State.ALARM_ON)],
    indirect=True,
)
async def test_twinguard_smoke_clears_and_unsubscribes(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_session: MagicMock
) -> None:
    """Alarm off clears the sensor; unloading removes the callback."""
    mock_session.api.get_messages.return_value = [
        _smoke_message("hdm:HomeMaticIP:twinguard1")
    ]
    await setup_integration(hass, mock_config_entry)
    system = mock_session.device_helper.smoke_detection_system
    service = system.device_services[0]
    assert hass.states.get("binary_sensor.twinguard_smoke").state == STATE_ON

    system.alarm = SurveillanceAlarmService.State.ALARM_OFF
    next(iter(service.callbacks.values()))()
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.twinguard_smoke").state == STATE_OFF

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert not service.callbacks


@pytest.mark.parametrize(
    "device_buckets",
    [_smoke_buckets(SurveillanceAlarmService.State.ALARM_ON)],
    indirect=True,
)
async def test_twinguard_smoke_message_fetch_fails(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_session: MagicMock
) -> None:
    """A failing message fetch keeps the previous state."""
    mock_session.api.get_messages.side_effect = OSError("boom")
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("binary_sensor.twinguard_smoke").state == STATE_OFF
