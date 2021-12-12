"""Test button of Nettigo Air Monitor integration."""
from unittest.mock import patch

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, ButtonDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.components.nam import init_integration


async def test_button(hass):
    """Test states of the button."""
    registry = er.async_get(hass)

    await init_integration(hass)

    state = hass.states.get("button.nettigo_air_monitor_restart")
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_DEVICE_CLASS) == ButtonDeviceClass.RESTART

    entry = registry.async_get("button.nettigo_air_monitor_restart")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-restart"


async def test_button_press(hass):
    """Test button press."""
    await init_integration(hass)

    now = dt_util.utcnow()
    with patch(
        "homeassistant.components.nam.NettigoAirMonitor.async_restart"
    ) as mock_restart, patch("homeassistant.core.dt_util.utcnow", return_value=now):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            "press",
            {ATTR_ENTITY_ID: "button.nettigo_air_monitor_restart"},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_restart.assert_called_once()

    state = hass.states.get("button.nettigo_air_monitor_restart")
    assert state
    assert state.state == now.isoformat()
