"""Test button of Nettigo Air Monitor integration."""

from unittest.mock import MagicMock, patch

from aiohttp.client_exceptions import ClientError
from nettigo_air_monitor import ApiError, AuthFailedError
import pytest
from pytest_homeassistant.common import MockConfigEntry

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

from . import setup_integration


@pytest.mark.usefixtures("mock_nam_client")
async def test_button(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test states of the button."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("button.nettigo_air_monitor_restart")
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_DEVICE_CLASS) == ButtonDeviceClass.RESTART

    entry = entity_registry.async_get("button.nettigo_air_monitor_restart")
    assert entry
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff-restart"


async def test_button_press(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nam_client: MagicMock,
) -> None:
    """Test button press."""
    await setup_integration(hass, mock_config_entry)

    now = dt_util.utcnow()
    with patch("homeassistant.core.dt_util.utcnow", return_value=now):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.nettigo_air_monitor_restart"},
            blocking=True,
        )
        await hass.async_block_till_done()

    mock_nam_client.async_restart.assert_called_once()

    state = hass.states.get("button.nettigo_air_monitor_restart")
    assert state
    assert state.state == now.isoformat()


@pytest.mark.parametrize(("exc"), [ApiError("API Error"), ClientError, TimeoutError])
async def test_button_press_exc(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nam_client: MagicMock,
    exc: Exception | type[Exception],
) -> None:
    """Test button press when exception occurs."""
    await setup_integration(hass, mock_config_entry)

    mock_nam_client.async_restart.side_effect = exc
    with pytest.raises(
        HomeAssistantError,
        match="An error occurred while calling action for"
        " button.nettigo_air_monitor_restart",
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.nettigo_air_monitor_restart"},
            blocking=True,
        )


async def test_button_press_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nam_client: MagicMock,
) -> None:
    """Test button press when auth error occurs."""
    await setup_integration(hass, mock_config_entry)

    mock_nam_client.async_restart.side_effect = AuthFailedError("auth error")
    with pytest.raises(
        HomeAssistantError,
        match="Authentication failed for 10.10.2.3",
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.nettigo_air_monitor_restart"},
            blocking=True,
        )

    assert mock_config_entry.state is ConfigEntryState.LOADED

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == mock_config_entry.entry_id
