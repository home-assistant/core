"""Fixtures for Envisalink tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from pyenvisalink import EnvisalinkAlarmPanel
from pyenvisalink.alarm_state import AlarmState
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

DOMAIN = "envisalink"

# The configured alarm code, shared with the tests so the service-call
# assertions stay in sync with the code HA injects as the default.
MOCK_CODE = "1234"

# Mirrors the legacy YAML config keys (CONF_USERNAME == "user_name", CONF_PASS
# == "password"). The integration is YAML-only (no config entry), so a future
# config-entry migration replaces this whole fixture.
MOCK_CONFIG = {
    DOMAIN: {
        "host": "1.2.3.4",
        "panel_type": "DSC",
        "user_name": "user",
        "password": "pass",
        "code": MOCK_CODE,
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
    login-success callback, so the mock's start() invokes it. Tests can
    reassign ``controller.start.side_effect`` to ``callback_login_failure`` or
    ``callback_login_timeout`` to exercise alternate connection outcomes.
    """
    controller = MagicMock(spec=EnvisalinkAlarmPanel)
    # (max_zones=64, max_partitions=8) — sized to the panel's hardware limits.
    controller.alarm_state = AlarmState.get_initial_alarm_state(64, 8)
    # A non-empty alpha makes the initial partition state DISARMED (not None).
    controller.alarm_state["partition"][1]["status"]["alpha"] = "Ready"
    controller.start.side_effect = lambda: controller.callback_login_success(None)

    with patch(
        "homeassistant.components.envisalink.EnvisalinkAlarmPanel",
        return_value=controller,
    ):
        yield controller


async def setup_envisalink(
    hass: HomeAssistant, config: ConfigType | None = None
) -> bool:
    """Set up the envisalink component and wait for it to finish."""
    result = await async_setup_component(hass, DOMAIN, config or MOCK_CONFIG)
    await hass.async_block_till_done()
    return result
