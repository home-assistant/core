"""The tests for the alarm control panel demo component."""

from collections.abc import AsyncGenerator
from unittest.mock import patch

import pytest

from homeassistant.components.alarm_control_panel import (
    DOMAIN as ALARM_CONTROL_PANEL_DOMAIN,
    AlarmControlPanelState,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

ENTITY_SECURITY = "alarm_control_panel.security"


@pytest.fixture
async def alarm_control_panel_only() -> AsyncGenerator[None]:
    """Enable only the alarm control panel platform."""
    with patch(
        "homeassistant.components.demo.COMPONENTS_WITH_CONFIG_ENTRY_DEMO_PLATFORM",
        [Platform.ALARM_CONTROL_PANEL],
    ):
        yield


@pytest.fixture(autouse=True)
async def setup_demo_alarm_control_panel(
    hass: HomeAssistant, alarm_control_panel_only
) -> None:
    """Initialize setup demo alarm control panel entity."""
    assert await async_setup_component(
        hass, ALARM_CONTROL_PANEL_DOMAIN, {"alarm_control_panel": {"platform": "demo"}}
    )
    await hass.async_block_till_done()


def test_setup_params(hass: HomeAssistant) -> None:
    """Test the initial parameters."""
    state = hass.states.get(ENTITY_SECURITY)
    assert state
    assert state.state == AlarmControlPanelState.DISARMED
