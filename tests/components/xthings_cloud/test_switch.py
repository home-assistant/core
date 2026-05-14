"""Tests for Xthings Cloud switch platform."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    Platform,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import get_device_by_id, setup_integration

from tests.common import MockConfigEntry


async def test_switches(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test switch entities are created correctly."""
    with patch("homeassistant.components.xthings_cloud.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)

    entry_50 = entity_registry.async_get("switch.smart_plug_50")
    assert entry_50 is not None
    assert entry_50.unique_id == "dev_plug_001"
    assert entry_50.platform == "xthings_cloud"
    assert entry_50.config_entry_id == mock_config_entry.entry_id

    entry_100 = entity_registry.async_get("switch.smart_plug_100")
    assert entry_100 is not None
    assert entry_100.unique_id == "dev_plug_002"
    assert entry_100.platform == "xthings_cloud"
    assert entry_100.config_entry_id == mock_config_entry.entry_id

    state_50 = hass.states.get("switch.smart_plug_50")
    assert state_50 is not None
    assert state_50.state == STATE_ON
    assert state_50.attributes["friendly_name"] == "Smart Plug 50"

    state_100 = hass.states.get("switch.smart_plug_100")
    assert state_100 is not None
    assert state_100.state == STATE_OFF
    assert state_100.attributes["friendly_name"] == "Smart Plug 100"


@pytest.mark.parametrize(
    ("service", "method"),
    [
        (SERVICE_TURN_ON, "async_plug_on"),
        (SERVICE_TURN_OFF, "async_plug_off"),
    ],
)
async def test_plug_turn_on_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    service: str,
    method: str,
) -> None:
    """Test turning on and off a plug."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: "switch.smart_plug_50"},
        blocking=True,
    )
    getattr(mock_api_client, method).assert_called_once_with("dev_plug_001")


async def test_plug_unavailable_when_offline(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
) -> None:
    """Test plug shows unavailable when device is offline."""
    get_device_by_id(mock_api_client, "dev_plug_001")["online"] = False
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("switch.smart_plug_50")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_updating_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    mock_websocket: AsyncMock,
) -> None:
    """Test updating state."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("switch.smart_plug_100")
    assert state is not None
    assert state.state == STATE_OFF

    mock_websocket.call_args[1]["on_device_status"](
        "dev_plug_002",
        {
            "on": True,
        },
    )

    state = hass.states.get("switch.smart_plug_100")
    assert state is not None
    assert state.state == STATE_ON
