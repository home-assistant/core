"""deCONZ alarm control panel platform tests."""

from collections.abc import Callable

from pydeconz.models.sensor.ancillary_control import AncillaryControlPanel
import pytest

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_CODE,
    ATTR_ENTITY_ID,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_ARM_NIGHT,
    SERVICE_ALARM_DISARM,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_ARMING,
    STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING,
    STATE_ALARM_TRIGGERED,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant

from .conftest import WebsocketDataType

from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.parametrize(
    "alarm_system_payload",
    [
        {
            "0": {
                "name": "default",
                "config": {
                    "armmode": "armed_away",
                    "configured": True,
                    "disarmed_entry_delay": 0,
                    "disarmed_exit_delay": 0,
                    "armed_away_entry_delay": 120,
                    "armed_away_exit_delay": 120,
                    "armed_away_trigger_duration": 120,
                    "armed_stay_entry_delay": 120,
                    "armed_stay_exit_delay": 120,
                    "armed_stay_trigger_duration": 120,
                    "armed_night_entry_delay": 120,
                    "armed_night_exit_delay": 120,
                    "armed_night_trigger_duration": 120,
                },
                "state": {"armstate": "armed_away", "seconds_remaining": 0},
                "devices": {
                    "00:00:00:00:00:00:00:00-00": {},
                    "00:15:8d:00:02:af:95:f9-01-0101": {
                        "armmask": "AN",
                        "trigger": "state/vibration",
                    },
                },
            }
        }
    ],
)
@pytest.mark.parametrize(
    "sensor_payload",
    [
        {
            "0": {
                "config": {
                    "battery": 95,
                    "enrolled": 1,
                    "on": True,
                    "pending": [],
                    "reachable": True,
                },
                "ep": 1,
                "etag": "5aaa1c6bae8501f59929539c6e8f44d6",
                "lastseen": "2021-07-25T18:07Z",
                "manufacturername": "lk",
                "modelid": "ZB-KeypadGeneric-D0002",
                "name": "Keypad",
                "state": {
                    "action": "armed_stay",
                    "lastupdated": "2021-07-25T18:02:51.172",
                    "lowbattery": False,
                    "panel": "none",
                    "seconds_remaining": 55,
                    "tampered": False,
                },
                "swversion": "3.13",
                "type": "ZHAAncillaryControl",
                "uniqueid": "00:00:00:00:00:00:00:00-00",
            }
        }
    ],
)
async def test_alarm_control_panel(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry_setup: ConfigEntry,
    mock_put_request: Callable[[str, str], AiohttpClientMocker],
    mock_websocket_data: WebsocketDataType,
) -> None:
    """Test successful creation of alarm control panel entities."""
    assert len(hass.states.async_all()) == 4
    assert hass.states.get("alarm_control_panel.keypad").state == STATE_UNKNOWN

    # Event signals alarm control panel armed away

    event_changed_sensor = {
        "r": "sensors",
        "state": {"panel": AncillaryControlPanel.ARMED_AWAY},
    }
    await mock_websocket_data(event_changed_sensor)
    await hass.async_block_till_done()

    assert hass.states.get("alarm_control_panel.keypad").state == STATE_ALARM_ARMED_AWAY

    # Event signals alarm control panel armed night

    event_changed_sensor = {
        "r": "sensors",
        "state": {"panel": AncillaryControlPanel.ARMED_NIGHT},
    }
    await mock_websocket_data(event_changed_sensor)
    await hass.async_block_till_done()

    assert (
        hass.states.get("alarm_control_panel.keypad").state == STATE_ALARM_ARMED_NIGHT
    )

    # Event signals alarm control panel armed home

    event_changed_sensor = {
        "r": "sensors",
        "state": {"panel": AncillaryControlPanel.ARMED_STAY},
    }
    await mock_websocket_data(event_changed_sensor)
    await hass.async_block_till_done()

    assert hass.states.get("alarm_control_panel.keypad").state == STATE_ALARM_ARMED_HOME

    # Event signals alarm control panel disarmed

    event_changed_sensor = {
        "r": "sensors",
        "state": {"panel": AncillaryControlPanel.DISARMED},
    }
    await mock_websocket_data(event_changed_sensor)
    await hass.async_block_till_done()

    assert hass.states.get("alarm_control_panel.keypad").state == STATE_ALARM_DISARMED

    # Event signals alarm control panel arming

    for arming_event in (
        AncillaryControlPanel.ARMING_AWAY,
        AncillaryControlPanel.ARMING_NIGHT,
        AncillaryControlPanel.ARMING_STAY,
    ):
        event_changed_sensor = {
            "r": "sensors",
            "state": {"panel": arming_event},
        }
        await mock_websocket_data(event_changed_sensor)
        await hass.async_block_till_done()

        assert hass.states.get("alarm_control_panel.keypad").state == STATE_ALARM_ARMING

    # Event signals alarm control panel pending

    for pending_event in (
        AncillaryControlPanel.ENTRY_DELAY,
        AncillaryControlPanel.EXIT_DELAY,
    ):
        event_changed_sensor = {
            "r": "sensors",
            "state": {"panel": pending_event},
        }
        await mock_websocket_data(event_changed_sensor)
        await hass.async_block_till_done()

        assert (
            hass.states.get("alarm_control_panel.keypad").state == STATE_ALARM_PENDING
        )

    # Event signals alarm control panel triggered

    event_changed_sensor = {
        "r": "sensors",
        "state": {"panel": AncillaryControlPanel.IN_ALARM},
    }
    await mock_websocket_data(event_changed_sensor)
    await hass.async_block_till_done()

    assert hass.states.get("alarm_control_panel.keypad").state == STATE_ALARM_TRIGGERED

    # Event signals alarm control panel unknown state keeps previous state

    event_changed_sensor = {
        "r": "sensors",
        "state": {"panel": AncillaryControlPanel.NOT_READY},
    }
    await mock_websocket_data(event_changed_sensor)
    await hass.async_block_till_done()

    assert hass.states.get("alarm_control_panel.keypad").state == STATE_ALARM_TRIGGERED

    # Verify service calls

    # Service set alarm to away mode

    aioclient_mock = mock_put_request("/alarmsystems/0/arm_away")

    await hass.services.async_call(
        ALARM_CONTROL_PANEL_DOMAIN,
        SERVICE_ALARM_ARM_AWAY,
        {ATTR_ENTITY_ID: "alarm_control_panel.keypad", ATTR_CODE: "1234"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[1][2] == {"code0": "1234"}

    # Service set alarm to home mode

    aioclient_mock = mock_put_request("/alarmsystems/0/arm_stay")

    await hass.services.async_call(
        ALARM_CONTROL_PANEL_DOMAIN,
        SERVICE_ALARM_ARM_HOME,
        {ATTR_ENTITY_ID: "alarm_control_panel.keypad", ATTR_CODE: "2345"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[2][2] == {"code0": "2345"}

    # Service set alarm to night mode

    aioclient_mock = mock_put_request("/alarmsystems/0/arm_night")

    await hass.services.async_call(
        ALARM_CONTROL_PANEL_DOMAIN,
        SERVICE_ALARM_ARM_NIGHT,
        {ATTR_ENTITY_ID: "alarm_control_panel.keypad", ATTR_CODE: "3456"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[3][2] == {"code0": "3456"}

    # Service set alarm to disarmed

    aioclient_mock = mock_put_request("/alarmsystems/0/disarm")

    await hass.services.async_call(
        ALARM_CONTROL_PANEL_DOMAIN,
        SERVICE_ALARM_DISARM,
        {ATTR_ENTITY_ID: "alarm_control_panel.keypad", ATTR_CODE: "4567"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[4][2] == {"code0": "4567"}

    await hass.config_entries.async_unload(config_entry_setup.entry_id)

    states = hass.states.async_all()
    assert len(states) == 4
    for state in states:
        assert state.state == STATE_UNAVAILABLE

    await hass.config_entries.async_remove(config_entry_setup.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0
