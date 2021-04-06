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
    ANCILLARY_CONTROL_IN_ALARM,
    ANCILLARY_CONTROL_NOT_READY,
)

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
)
from homeassistant.components.deconz.alarm_control_panel import (
    SERVICE_ALARM_ARMING_AWAY,
    SERVICE_ALARM_ARMING_HOME,
    SERVICE_ALARM_ARMING_NIGHT,
    SERVICE_ALARM_ENTRY_DELAY,
    SERVICE_ALARM_EXIT_DELAY,
    SERVICE_ALARM_NOT_READY,
    SERVICE_ALARM_TRIGGERED,
)
from homeassistant.components.deconz.const import DOMAIN as DECONZ_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_ALARM_ARM_AWAY,
    SERVICE_ALARM_ARM_HOME,
    SERVICE_ALARM_ARM_NIGHT,
    SERVICE_ALARM_DISARM,
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
                    "panel": "disarmed",
                    "tampered": True,
                },
                "type": "ZHAAncillaryControl",
                "uniqueid": "00:0d:6f:00:13:4f:61:39-01-0501",
            }
        }
    }
    with patch.dict(DECONZ_WEB_REQUEST, data):
        config_entry = await setup_deconz_integration(hass, aioclient_mock)

    assert len(hass.states.async_all()) == 1
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
    assert aioclient_mock.mock_calls[1][2] == {"armed": ANCILLARY_CONTROL_ARMED_AWAY}

    # Service set alarm to home mode

    await hass.services.async_call(
        ALARM_CONTROL_PANEL_DOMAIN,
        SERVICE_ALARM_ARM_HOME,
        {ATTR_ENTITY_ID: "alarm_control_panel.keypad"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[2][2] == {"armed": ANCILLARY_CONTROL_ARMED_STAY}

    # Service set alarm to night mode

    await hass.services.async_call(
        ALARM_CONTROL_PANEL_DOMAIN,
        SERVICE_ALARM_ARM_NIGHT,
        {ATTR_ENTITY_ID: "alarm_control_panel.keypad"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[3][2] == {"armed": ANCILLARY_CONTROL_ARMED_NIGHT}

    # Service set alarm to disarmed

    await hass.services.async_call(
        ALARM_CONTROL_PANEL_DOMAIN,
        SERVICE_ALARM_DISARM,
        {ATTR_ENTITY_ID: "alarm_control_panel.keypad"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[4][2] == {"armed": ANCILLARY_CONTROL_DISARMED}

    # Custom services

    # Service set alarm to arming away

    await hass.services.async_call(
        DECONZ_DOMAIN,
        SERVICE_ALARM_ARMING_AWAY,
        {ATTR_ENTITY_ID: "alarm_control_panel.keypad"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[5][2] == {"armed": ANCILLARY_CONTROL_ARMING_AWAY}

    # Service set alarm to arming home

    await hass.services.async_call(
        DECONZ_DOMAIN,
        SERVICE_ALARM_ARMING_HOME,
        {ATTR_ENTITY_ID: "alarm_control_panel.keypad"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[6][2] == {"armed": ANCILLARY_CONTROL_ARMING_STAY}

    # Service set alarm to arming night

    await hass.services.async_call(
        DECONZ_DOMAIN,
        SERVICE_ALARM_ARMING_NIGHT,
        {ATTR_ENTITY_ID: "alarm_control_panel.keypad"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[7][2] == {"armed": ANCILLARY_CONTROL_ARMING_NIGHT}

    # Service set alarm to entry delay

    await hass.services.async_call(
        DECONZ_DOMAIN,
        SERVICE_ALARM_ENTRY_DELAY,
        {ATTR_ENTITY_ID: "alarm_control_panel.keypad"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[8][2] == {"armed": ANCILLARY_CONTROL_ENTRY_DELAY}

    # Service set alarm to exit delay

    await hass.services.async_call(
        DECONZ_DOMAIN,
        SERVICE_ALARM_EXIT_DELAY,
        {ATTR_ENTITY_ID: "alarm_control_panel.keypad"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[9][2] == {"armed": ANCILLARY_CONTROL_EXIT_DELAY}

    # Service set alarm to not ready

    await hass.services.async_call(
        DECONZ_DOMAIN,
        SERVICE_ALARM_NOT_READY,
        {ATTR_ENTITY_ID: "alarm_control_panel.keypad"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[10][2] == {"armed": ANCILLARY_CONTROL_NOT_READY}

    # Service set alarm to triggered

    await hass.services.async_call(
        DECONZ_DOMAIN,
        SERVICE_ALARM_TRIGGERED,
        {ATTR_ENTITY_ID: "alarm_control_panel.keypad"},
        blocking=True,
    )
    assert aioclient_mock.mock_calls[11][2] == {"armed": ANCILLARY_CONTROL_IN_ALARM}

    await hass.config_entries.async_unload(config_entry.entry_id)

    states = hass.states.async_all()
    assert len(states) == 1
    for state in states:
        assert state.state == STATE_UNAVAILABLE

    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0
