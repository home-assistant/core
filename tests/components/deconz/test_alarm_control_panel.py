"""deCONZ alarm control panel platform tests."""

from collections.abc import Callable
from unittest.mock import patch

from pydeconz.models.sensor.ancillary_control import AncillaryControlPanel
import pytest
from syrupy import SnapshotAssertion

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
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import ConfigEntryFactoryType, WebsocketDataType

from tests.common import snapshot_platform
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
    ],
)
async def test_alarm_control_panel(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    config_entry_factory: ConfigEntryFactoryType,
    mock_put_request: Callable[[str, str], AiohttpClientMocker],
    sensor_ws_data: WebsocketDataType,
    snapshot: SnapshotAssertion,
) -> None:
    """Test successful creation of alarm control panel entities."""
    with patch(
        "homeassistant.components.deconz.PLATFORMS", [Platform.ALARM_CONTROL_PANEL]
    ):
        config_entry = await config_entry_factory()
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)

    for action, state in (
        # Event signals alarm control panel armed state
        (AncillaryControlPanel.ARMED_AWAY, STATE_ALARM_ARMED_AWAY),
        (AncillaryControlPanel.ARMED_NIGHT, STATE_ALARM_ARMED_NIGHT),
        (AncillaryControlPanel.ARMED_STAY, STATE_ALARM_ARMED_HOME),
        (AncillaryControlPanel.DISARMED, STATE_ALARM_DISARMED),
        # Event signals alarm control panel arming state
        (AncillaryControlPanel.ARMING_AWAY, STATE_ALARM_ARMING),
        (AncillaryControlPanel.ARMING_NIGHT, STATE_ALARM_ARMING),
        (AncillaryControlPanel.ARMING_STAY, STATE_ALARM_ARMING),
        # Event signals alarm control panel pending state
        (AncillaryControlPanel.ENTRY_DELAY, STATE_ALARM_PENDING),
        (AncillaryControlPanel.EXIT_DELAY, STATE_ALARM_PENDING),
        # Event signals alarm control panel triggered state
        (AncillaryControlPanel.IN_ALARM, STATE_ALARM_TRIGGERED),
        # Event signals alarm control panel unknown state keeps previous state
        (AncillaryControlPanel.NOT_READY, STATE_ALARM_TRIGGERED),
    ):
        await sensor_ws_data({"state": {"panel": action}})
        assert hass.states.get("alarm_control_panel.keypad").state == state

    # Verify service calls

    for path, service, code in (
        # Service set alarm to away mode
        ("arm_away", SERVICE_ALARM_ARM_AWAY, "1234"),
        # Service set alarm to home mode
        ("arm_stay", SERVICE_ALARM_ARM_HOME, "2345"),
        # Service set alarm to night mode
        ("arm_night", SERVICE_ALARM_ARM_NIGHT, "3456"),
        # Service set alarm to disarmed
        ("disarm", SERVICE_ALARM_DISARM, "4567"),
    ):
        aioclient_mock.mock_calls.clear()
        aioclient_mock = mock_put_request(f"/alarmsystems/0/{path}")
        await hass.services.async_call(
            ALARM_CONTROL_PANEL_DOMAIN,
            service,
            {ATTR_ENTITY_ID: "alarm_control_panel.keypad", ATTR_CODE: code},
            blocking=True,
        )
        assert aioclient_mock.mock_calls[0][2] == {"code0": code}
