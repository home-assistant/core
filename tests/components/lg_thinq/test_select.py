"""Tests for the LG ThinQ select platform."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.select import ATTR_OPTIONS
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("device_fixture", ["washtower_dryer"])
async def test_washtower_dryer_operation_select(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a WashTower dryer gets an operation select entity."""
    with patch("homeassistant.components.lg_thinq.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, mock_config_entry)

    state = hass.states.get("select.test_washtower_dryer_operation")
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_OPTIONS] == [
        "start",
        "stop",
        "power_off",
        "power_on",
    ]
