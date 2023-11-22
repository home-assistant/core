"""Test Acaia buttons."""
from unittest.mock import patch

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import init_integration


async def test_button(hass: HomeAssistant) -> None:
    """Test states of the button."""
    registry = er.async_get(hass)

    await init_integration(hass)

    state = hass.states.get("button.lunar_1234_tare")
    assert state
    assert state.state == STATE_UNKNOWN

    entry = registry.async_get("button.lunar_1234_tare")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff_tare"

    state = hass.states.get("button.lunar_1234_reset_timer")
    assert state
    assert state.state == STATE_UNKNOWN

    entry = registry.async_get("button.lunar_1234_reset_timer")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff_reset_timer"

    state = hass.states.get("button.lunar_1234_start_stop_timer")
    assert state
    assert state.state == STATE_UNKNOWN

    entry = registry.async_get("button.lunar_1234_start_stop_timer")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff_start_stop"


async def test_button_press(hass: HomeAssistant) -> None:
    """Test a button press to."""
    await init_integration(hass)

    now = dt_util.utcnow()
    with patch(
        "homeassistant.components.acaia.coordinator.AcaiaClient.tare"
    ) as mock_tare, patch("homeassistant.core.dt_util.utcnow", return_value=now):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.lunar_1234_tare"},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_tare.assert_called_once()

    state = hass.states.get("button.lunar_1234_tare")
    assert state
    assert state.state == now.isoformat()

    with patch(
        "homeassistant.components.acaia.coordinator.AcaiaClient.reset_timer"
    ) as mock_reset_timer, patch("homeassistant.core.dt_util.utcnow", return_value=now):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.lunar_1234_reset_timer"},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_reset_timer.assert_called_once()

    state = hass.states.get("button.lunar_1234_reset_timer")
    assert state
    assert state.state == now.isoformat()

    with patch(
        "homeassistant.components.acaia.coordinator.AcaiaClient.start_stop_timer"
    ) as mock_start_stop_timer, patch(
        "homeassistant.core.dt_util.utcnow", return_value=now
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.lunar_1234_start_stop_timer"},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_start_stop_timer.assert_called_once()

    state = hass.states.get("button.lunar_1234_start_stop_timer")
    assert state
    assert state.state == now.isoformat()
