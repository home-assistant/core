"""Fixtures for Envisalink tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from pyenvisalink import EnvisalinkAlarmPanel
from pyenvisalink.alarm_state import AlarmState
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

DOMAIN = "envisalink"

# Mirrors the YAML config keys (CONF_USERNAME == "user_name", CONF_PASS == "password").
MOCK_CONFIG = {
    DOMAIN: {
        "host": "1.2.3.4",
        "panel_type": "DSC",
        "user_name": "user",
        "password": "pass",
        "code": "1234",
        "partitions": {1: {"name": "Main Home"}},
        "zones": {1: {"name": "Front Door", "type": "door"}},
    }
}

# Entity ids derived from the configured names.
ALARM_ENTITY = "alarm_control_panel.main_home"
KEYPAD_ENTITY = "sensor.main_home_keypad"
ZONE_ENTITY = "binary_sensor.front_door"


@pytest.fixture
def mock_controller() -> Generator[MagicMock]:
    """Patch EnvisalinkAlarmPanel with a spec'd mock controller.

    The integration waits on a connection future that is resolved by the
    login-success callback, so the mock's start() invokes it.
    """
    controller = MagicMock(spec=EnvisalinkAlarmPanel)
    controller.alarm_state = AlarmState.get_initial_alarm_state(64, 8)
    # A non-empty alpha makes the initial partition state DISARMED (not None).
    controller.alarm_state["partition"][1]["status"]["alpha"] = "Ready"
    controller.start.side_effect = lambda: controller.callback_login_success(None)

    with patch(
        "homeassistant.components.envisalink.EnvisalinkAlarmPanel",
        return_value=controller,
    ):
        yield controller


async def setup_envisalink(hass: HomeAssistant, config: dict | None = None) -> bool:
    """Set up the envisalink component and wait for it to finish."""
    result = await async_setup_component(hass, DOMAIN, config or MOCK_CONFIG)
    await hass.async_block_till_done()
    return result
