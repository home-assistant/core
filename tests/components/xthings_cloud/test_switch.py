"""Tests for Xthings Cloud switch platform."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import get_device_by_id, setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_switches(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test switch entities are created correctly."""
    with patch("homeassistant.components.xthings_cloud.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)

        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


@pytest.mark.parametrize(
    ("entity_id", "device_id", "service", "method"),
    [
        (
            "switch.smart_plug_50",
            "dev_plug_001",
            SERVICE_TURN_ON,
            "async_plug_on",
        ),
        (
            "switch.smart_plug_50",
            "dev_plug_001",
            SERVICE_TURN_OFF,
            "async_plug_off",
        ),
    ],
)
async def test_turn_on_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    entity_id: str,
    device_id: str,
    service: str,
    method: str,
) -> None:
    """Test turning on and off a device."""
    with patch("homeassistant.components.xthings_cloud.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    getattr(mock_api_client, method).assert_called_once_with(device_id)


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
