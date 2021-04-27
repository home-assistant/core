"""deCONZ alarm control panel platform tests."""

from unittest.mock import patch

from pydeconz.sensor import (
    ANCILLARY_CONTROL_ARMED_AWAY,
    ANCILLARY_CONTROL_ARMED_NIGHT,
    ANCILLARY_CONTROL_ARMED_STAY,
    ANCILLARY_CONTROL_ARMING_AWAY,
    ANCILLARY_CONTROL_ARMING_NIGHT,
    ANCILLARY_CONTROL_ARMING_STAY,
    ANCILLARY_CONTROL_DISARMED,
    ANCILLARY_CONTROL_ENTRY_DELAY,
    ANCILLARY_CONTROL_EXIT_DELAY,
    ANCILLARY_CONTROL_NOT_READY_TO_ARM,
)

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
)
from homeassistant.components.deconz.alarm_control_panel import (
    CONF_ALARM_PANEL_STATE,
    PANEL_ARMING_AWAY,
    PANEL_ARMING_HOME,
    PANEL_ARMING_NIGHT,
    PANEL_ENTRY_DELAY,
    PANEL_EXIT_DELAY,
    PANEL_NOT_READY_TO_ARM,
    SERVICE_ALARM_PANEL_STATE,
)
from homeassistant.components.deconz.const import DOMAIN as DECONZ_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_ARM_NIGHT,
    SERVICE_ALARM_DISARM,
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
    STATE_UNAVAILABLE,
)

from .test_gateway import (
    DECONZ_WEB_REQUEST,
    mock_deconz_put_request,
    setup_deconz_integration,
)


async def test_no_sensors(hass, aioclient_mock):
    """Test that no sensors in deconz results in no climate entities."""
    await setup_deconz_integration(hass, aioclient_mock)
    assert len(hass.states.async_all()) == 0


async def test_alarm_control_panel(hass, aioclient_mock, mock_deconz_websocket):
    """Test successful creation of alarm control panel entities."""
    data = {
        "sensors": {
            "0": {
                "config": {
                    "armed": "disarmed",
                    "enrolled": 0,
                    "on": True,
                    "panel": "disarmed",
                    "pending": [],
                    "reachable": True,
                },
                "ep": 1,
                "etag": "3c4008d74035dfaa1f0bb30d24468b12",
                "lastseen": "2021-04-02T13:07Z",
                "manufacturername": "Universal Electronics Inc",
                "modelid": "URC4450BC0-X-R",
                "name": "Keypad",
                "state": {
                    "action": "armed_away,1111,55",
                    "lastupdated": "2021-04-02T13:08:18.937",
                    "lowbattery": False,
                    "tampered": True,
                },
                "type": "ZHAAncillaryControl",
                "uniqueid": "00:0d:6f:00:13:4f:61:39-01-0501",
            }
        }
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        config_entry = await setup_deconz_integration(hass, aioclient_mock)

    assert len(hass.states.async_all()) == 2
    assert hass.states.get("alarm_control_panel.keypad").state == STATE_ALARM_DISARMED

    # Event signals alarm control panel armed away

    event_changed_sensor = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "0",
        "config": {"armed": ANCILLARY_CONTROL_ARMED_AWAY},
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
        "config": {"armed": ANCILLARY_CONTROL_ARMED_NIGHT},
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
        "config": {"armed": ANCILLARY_CONTROL_ARMED_STAY},
    }
    await mock_deconz_websocket(data=event_changed_sensor)
    await hass.async_block_till_done()

    assert hass.states.get("alarm_control_panel.keypad").state == STATE_ALARM_ARMED_HOME

    # Event signals alarm control panel armed night

    event_changed_sensor = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "0",
        "config": {"armed": ANCILLARY_CONTROL_ARMED_NIGHT},
    }
    await mock_deconz_websocket(data=event_changed_sensor)
    await hass.async_block_till_done()

    assert (
        hass.states.get("alarm_control_panel.keypad").state == STATE_ALARM_ARMED_NIGHT
    )

    # Event signals alarm control panel disarmed

    event_changed_sensor = {
        "t": "event",
        "e": "changed",
        "r": "sensors",
        "id": "0",
        "config": {"armed": ANCILLARY_CONTROL_DISARMED},
    }
    await mock_deconz_websocket(data=event_changed_sensor)
    await hass.async_block_till_done()

    assert hass.states.get("alarm_control_panel.keypad").state == STATE_ALARM_DISARMED

    # Verify service calls

    mock_deconz_put_request(aioclient_mock, config_entry.data, "/sensors/0/config")

    # Service set alarm to away mode

    await hass.services.async_call(
        ALARM_CONTROL_PANEL_DOMAIN,
        SERVICE_ALARM_ARM_AWAY,
        {ATTR_ENTITY_ID: "alarm_control_panel.keypad"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[1][2] == {
        "armed": ANCILLARY_CONTROL_ARMED_AWAY,
        "panel": ANCILLARY_CONTROL_ARMED_AWAY,
    }

    # Service set alarm to home mode

    await hass.services.async_call(
        ALARM_CONTROL_PANEL_DOMAIN,
        SERVICE_ALARM_ARM_HOME,
        {ATTR_ENTITY_ID: "alarm_control_panel.keypad"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[2][2] == {
        "armed": ANCILLARY_CONTROL_ARMED_STAY,
        "panel": ANCILLARY_CONTROL_ARMED_STAY,
    }

    # Service set alarm to night mode

    await hass.services.async_call(
        ALARM_CONTROL_PANEL_DOMAIN,
        SERVICE_ALARM_ARM_NIGHT,
        {ATTR_ENTITY_ID: "alarm_control_panel.keypad"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[3][2] == {
        "armed": ANCILLARY_CONTROL_ARMED_NIGHT,
        "panel": ANCILLARY_CONTROL_ARMED_NIGHT,
    }

    # Service set alarm to disarmed

    await hass.services.async_call(
        ALARM_CONTROL_PANEL_DOMAIN,
        SERVICE_ALARM_DISARM,
        {ATTR_ENTITY_ID: "alarm_control_panel.keypad"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[4][2] == {
        "armed": ANCILLARY_CONTROL_DISARMED,
        "panel": ANCILLARY_CONTROL_DISARMED,
    }

    # Verify entity service calls

    # Service set panel to arming away

    await hass.services.async_call(
        DECONZ_DOMAIN,
        SERVICE_ALARM_PANEL_STATE,
        {
            ATTR_ENTITY_ID: "alarm_control_panel.keypad",
            CONF_ALARM_PANEL_STATE: PANEL_ARMING_AWAY,
        },
        blocking=True,
    )
    assert aioclient_mock.mock_calls[5][2] == {"panel": ANCILLARY_CONTROL_ARMING_AWAY}

    # Service set panel to arming home

    await hass.services.async_call(
        DECONZ_DOMAIN,
        SERVICE_ALARM_PANEL_STATE,
        {
            ATTR_ENTITY_ID: "alarm_control_panel.keypad",
            CONF_ALARM_PANEL_STATE: PANEL_ARMING_HOME,
        },
        blocking=True,
    )
    assert aioclient_mock.mock_calls[6][2] == {"panel": ANCILLARY_CONTROL_ARMING_STAY}

    # Service set panel to arming night

    await hass.services.async_call(
        DECONZ_DOMAIN,
        SERVICE_ALARM_PANEL_STATE,
        {
            ATTR_ENTITY_ID: "alarm_control_panel.keypad",
            CONF_ALARM_PANEL_STATE: PANEL_ARMING_NIGHT,
        },
        blocking=True,
    )
    assert aioclient_mock.mock_calls[7][2] == {"panel": ANCILLARY_CONTROL_ARMING_NIGHT}

    # Service set panel to entry delay

    await hass.services.async_call(
        DECONZ_DOMAIN,
        SERVICE_ALARM_PANEL_STATE,
        {
            ATTR_ENTITY_ID: "alarm_control_panel.keypad",
            CONF_ALARM_PANEL_STATE: PANEL_ENTRY_DELAY,
        },
        blocking=True,
    )
    assert aioclient_mock.mock_calls[8][2] == {"panel": ANCILLARY_CONTROL_ENTRY_DELAY}

    # Service set panel to exit delay

    await hass.services.async_call(
        DECONZ_DOMAIN,
        SERVICE_ALARM_PANEL_STATE,
        {
            ATTR_ENTITY_ID: "alarm_control_panel.keypad",
            CONF_ALARM_PANEL_STATE: PANEL_EXIT_DELAY,
        },
        blocking=True,
    )
    assert aioclient_mock.mock_calls[9][2] == {"panel": ANCILLARY_CONTROL_EXIT_DELAY}

    # Service set panel to not ready to arm

    await hass.services.async_call(
        DECONZ_DOMAIN,
        SERVICE_ALARM_PANEL_STATE,
        {
            ATTR_ENTITY_ID: "alarm_control_panel.keypad",
            CONF_ALARM_PANEL_STATE: PANEL_NOT_READY_TO_ARM,
        },
        blocking=True,
    )
    assert aioclient_mock.mock_calls[10][2] == {
        "panel": ANCILLARY_CONTROL_NOT_READY_TO_ARM
    }

    await hass.config_entries.async_unload(config_entry.entry_id)

    states = hass.states.async_all()
    assert len(states) == 2
    for state in states:
        assert state.state == STATE_UNAVAILABLE

    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0
