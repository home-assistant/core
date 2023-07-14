"""Test button of NextDNS integration."""
from unittest.mock import patch

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import init_integration


async def test_button(hass: HomeAssistant) -> None:
    """Test states of the button."""
    registry = er.async_get(hass)

    await init_integration(hass)

    state = hass.states.get("button.fake_profile_clear_logs")
    assert state
    assert state.state == STATE_UNKNOWN

    entry = registry.async_get("button.fake_profile_clear_logs")
    assert entry
    assert entry.unique_id == "xyz12_clear_logs"


async def test_button_press(hass: HomeAssistant) -> None:
    """Test button press."""
    await init_integration(hass)

    now = dt_util.utcnow()
    with patch(
        "homeassistant.components.nextdns.NextDns.clear_logs"
    ) as mock_clear_logs, patch("homeassistant.core.dt_util.utcnow", return_value=now):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            "press",
            {ATTR_ENTITY_ID: "button.fake_profile_clear_logs"},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_clear_logs.assert_called_once()

    state = hass.states.get("button.fake_profile_clear_logs")
    assert state
    assert state.state == now.isoformat()
