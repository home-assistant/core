"""Test button of Nettigo Air Monitor integration."""
from unittest.mock import patch

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, ATTR_ICON
from homeassistant.helpers import entity_registry as er

from tests.components.nam import init_integration


async def test_button(hass):
    """Test states of the button."""
    registry = er.async_get(hass)

    await init_integration(hass)

    state = hass.states.get("button.nettigo_air_monitor_restart")
    assert state
    assert state.state == "unknown"
    assert state.attributes.get(ATTR_ICON) == "mdi:restart"

    entry = registry.async_get("button.nettigo_air_monitor_restart")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-restart"


async def test_button_press(hass):
    """Test button press."""
    await init_integration(hass)

    with patch(
        "homeassistant.components.nam.NettigoAirMonitor.async_restart"
    ) as mock_restart:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            "press",
            {ATTR_ENTITY_ID: "button.nettigo_air_monitor_restart"},
            blocking=True,
        )

        mock_restart.assert_called_once()
