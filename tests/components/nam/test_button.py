"""Test button of Nettigo Air Monitor integration."""

from unittest.mock import patch

from aiohttp.client_exceptions import ClientError
from nettigo_air_monitor import ApiError, AuthFailedError
import pytest

from homeassistant.components.button import (
    DOMAIN as BUTTON_DOMAIN,
    SERVICE_PRESS,
    ButtonDeviceClass,
)
from homeassistant.components.nam import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import ATTR_DEVICE_CLASS, ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import init_integration


async def test_button(hass: HomeAssistant, entity_registry: er.EntityRegistry) -> None:
    """Test states of the button."""
    await init_integration(hass)

    state = hass.states.get("button.nettigo_air_monitor_restart")
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_DEVICE_CLASS) == ButtonDeviceClass.RESTART

    entry = entity_registry.async_get("button.nettigo_air_monitor_restart")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-restart"


async def test_button_press(hass: HomeAssistant) -> None:
    """Test button press."""
    await init_integration(hass)

    now = dt_util.utcnow()
    with (
        patch(
            "homeassistant.components.nam.NettigoAirMonitor.async_restart"
        ) as mock_restart,
        patch("homeassistant.core.dt_util.utcnow", return_value=now),
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.nettigo_air_monitor_restart"},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_restart.assert_called_once()

    state = hass.states.get("button.nettigo_air_monitor_restart")
    assert state
    assert state.state == now.isoformat()


@pytest.mark.parametrize(("exc"), [ApiError("API Error"), ClientError])
async def test_button_press_exc(hass: HomeAssistant, exc: Exception) -> None:
    """Test button press when exception occurs."""
    await init_integration(hass)

    with (
        patch(
            "homeassistant.components.nam.NettigoAirMonitor.async_restart",
            side_effect=exc,
        ),
        pytest.raises(
            HomeAssistantError,
            match="An error occurred while calling action for button.nettigo_air_monitor_restart",
        ),
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.nettigo_air_monitor_restart"},
            blocking=True,
        )


async def test_button_press_auth_error(hass: HomeAssistant) -> None:
    """Test button press when auth error occurs."""
    entry = await init_integration(hass)

    with patch(
        "homeassistant.components.nam.NettigoAirMonitor.async_restart",
        side_effect=AuthFailedError("auth error"),
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.nettigo_air_monitor_restart"},
            blocking=True,
        )

    assert entry.state is ConfigEntryState.LOADED

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == entry.entry_id
