"""deCONZ alarm control panel platform tests."""

from unittest.mock import patch

from pydeconz.models.sensor.ancillary_control import AncillaryControlPanel

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
)
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

from .test_gateway import (
    DECONZ_WEB_REQUEST,
    mock_deconz_put_request,
    setup_deconz_integration,
)

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_no_sensors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that no sensors in deconz results in no climate entities."""
    await setup_deconz_integration(hass, aioclient_mock)
    assert len(hass.states.async_all()) == 0


async def test_alarm_control_panel(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_deconz_websocket
) -> None:
    """Test successful creation of alarm control panel entities."""
    data = {
        "alarmsystems": {
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
        },
        "sensors": {
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
        },
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        config_entry = await setup_deconz_integration(hass, aioclient_mock)

    assert len(hass.states.async_all()) == 4
    assert hass.states.get("alarm_control_panel.keypad").state == STATE_UNKNOWN

    # Event signals alarm control panel armed away

    event_changed_sensor = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "0",
        "state": {"panel": AncillaryControlPanel.ARMED_AWAY},
    }
    await mock_deconz_websocket(data=event_changed_sensor)
    await hass.async_block_till_done()

    assert hass.states.get("alarm_control_panel.keypad").state == STATE_ALARM_ARMED_AWAY

    # Event signals alarm control panel armed night

    event_changed_sensor = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "0",
        "state": {"panel": AncillaryControlPanel.ARMED_NIGHT},
    }
    await mock_deconz_websocket(data=event_changed_sensor)
    await hass.async_block_till_done()

    assert (
        hass.states.get("alarm_control_panel.keypad").state == STATE_ALARM_ARMED_NIGHT
    )

    # Event signals alarm control panel armed home

    event_changed_sensor = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "0",
        "state": {"panel": AncillaryControlPanel.ARMED_STAY},
    }
    await mock_deconz_websocket(data=event_changed_sensor)
    await hass.async_block_till_done()

    assert hass.states.get("alarm_control_panel.keypad").state == STATE_ALARM_ARMED_HOME

    # Event signals alarm control panel disarmed

    event_changed_sensor = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "0",
        "state": {"panel": AncillaryControlPanel.DISARMED},
    }
    await mock_deconz_websocket(data=event_changed_sensor)
    await hass.async_block_till_done()

    assert hass.states.get("alarm_control_panel.keypad").state == STATE_ALARM_DISARMED

    # Event signals alarm control panel arming

    for arming_event in (
        AncillaryControlPanel.ARMING_AWAY,
        AncillaryControlPanel.ARMING_NIGHT,
        AncillaryControlPanel.ARMING_STAY,
    ):
        event_changed_sensor = {
            "t": "event",
            "e": "changed",
            "r": "sensors",
            "id": "0",
            "state": {"panel": arming_event},
        }
        await mock_deconz_websocket(data=event_changed_sensor)
        await hass.async_block_till_done()

        assert hass.states.get("alarm_control_panel.keypad").state == STATE_ALARM_ARMING

    # Event signals alarm control panel pending

    for pending_event in (
        AncillaryControlPanel.ENTRY_DELAY,
        AncillaryControlPanel.EXIT_DELAY,
    ):
        event_changed_sensor = {
            "t": "event",
            "e": "changed",
            "r": "sensors",
            "id": "0",
            "state": {"panel": pending_event},
        }
        await mock_deconz_websocket(data=event_changed_sensor)
        await hass.async_block_till_done()

        assert (
            hass.states.get("alarm_control_panel.keypad").state == STATE_ALARM_PENDING
        )

    # Event signals alarm control panel triggered

    event_changed_sensor = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "0",
        "state": {"panel": AncillaryControlPanel.IN_ALARM},
    }
    await mock_deconz_websocket(data=event_changed_sensor)
    await hass.async_block_till_done()

    assert hass.states.get("alarm_control_panel.keypad").state == STATE_ALARM_TRIGGERED

    # Event signals alarm control panel unknown state keeps previous state

    event_changed_sensor = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "0",
        "state": {"panel": AncillaryControlPanel.NOT_READY},
    }
    await mock_deconz_websocket(data=event_changed_sensor)
    await hass.async_block_till_done()

    assert hass.states.get("alarm_control_panel.keypad").state == STATE_ALARM_TRIGGERED

    # Verify service calls

    # Service set alarm to away mode

    mock_deconz_put_request(
        aioclient_mock, config_entry.data, "/alarmsystems/0/arm_away"
    )

    await hass.services.async_call(
        ALARM_CONTROL_PANEL_DOMAIN,
        SERVICE_ALARM_ARM_AWAY,
        {ATTR_ENTITY_ID: "alarm_control_panel.keypad", ATTR_CODE: "1234"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[1][2] == {"code0": "1234"}

    # Service set alarm to home mode

    mock_deconz_put_request(
        aioclient_mock, config_entry.data, "/alarmsystems/0/arm_stay"
    )

    await hass.services.async_call(
        ALARM_CONTROL_PANEL_DOMAIN,
        SERVICE_ALARM_ARM_HOME,
        {ATTR_ENTITY_ID: "alarm_control_panel.keypad", ATTR_CODE: "2345"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[2][2] == {"code0": "2345"}

    # Service set alarm to night mode

    mock_deconz_put_request(
        aioclient_mock, config_entry.data, "/alarmsystems/0/arm_night"
    )

    await hass.services.async_call(
        ALARM_CONTROL_PANEL_DOMAIN,
        SERVICE_ALARM_ARM_NIGHT,
        {ATTR_ENTITY_ID: "alarm_control_panel.keypad", ATTR_CODE: "3456"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[3][2] == {"code0": "3456"}

    # Service set alarm to disarmed

    mock_deconz_put_request(aioclient_mock, config_entry.data, "/alarmsystems/0/disarm")

    await hass.services.async_call(
        ALARM_CONTROL_PANEL_DOMAIN,
        SERVICE_ALARM_DISARM,
        {ATTR_ENTITY_ID: "alarm_control_panel.keypad", ATTR_CODE: "4567"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[4][2] == {"code0": "4567"}

    await hass.config_entries.async_unload(config_entry.entry_id)

    states = hass.states.async_all()
    assert len(states) == 4
    for state in states:
        assert state.state == STATE_UNAVAILABLE

    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0
