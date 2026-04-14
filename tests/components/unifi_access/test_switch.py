"""Tests for the UniFi Access switch platform."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from unifi_access_api import (
    ApiAuthError,
    ApiConnectionError,
    ApiError,
    ApiSSLError,
    EmergencyStatus,
)
from unifi_access_api.models.websocket import SettingUpdate, SettingUpdateData

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

EVACUATION_ENTITY = "switch.unifi_access_evacuation"
LOCKDOWN_ENTITY = "switch.unifi_access_lockdown"


def _get_ws_handlers(
    mock_client: MagicMock,
) -> dict[str, Callable[[object], Awaitable[None]]]:
    """Extract WebSocket handlers from mock client."""
    return mock_client.start_websocket.call_args[0][0]


def _get_on_disconnect(mock_client: MagicMock) -> Callable[[], Any]:
    """Extract on_disconnect callback from mock client."""
    return mock_client.start_websocket.call_args[1]["on_disconnect"]


def _get_on_connect(mock_client: MagicMock) -> Callable[[], Any]:
    """Extract on_connect callback from mock client."""
    return mock_client.start_websocket.call_args[1]["on_connect"]


async def test_switch_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test switch entities are created with expected state."""
    with patch("homeassistant.components.unifi_access.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "expected_status"),
    [
        (EVACUATION_ENTITY, EmergencyStatus(evacuation=True, lockdown=False)),
        (LOCKDOWN_ENTITY, EmergencyStatus(evacuation=False, lockdown=True)),
    ],
)
async def test_turn_on_switch(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    entity_id: str,
    expected_status: EmergencyStatus,
) -> None:
    """Test turning on emergency switch."""
    assert hass.states.get(entity_id).state == "off"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_client.set_emergency_status.assert_awaited_once_with(expected_status)
    assert hass.states.get(entity_id).state == "on"


@pytest.mark.parametrize(
    ("entity_id", "expected_status"),
    [
        (EVACUATION_ENTITY, EmergencyStatus(evacuation=False, lockdown=False)),
        (LOCKDOWN_ENTITY, EmergencyStatus(evacuation=False, lockdown=False)),
    ],
)
async def test_turn_off_switch(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    entity_id: str,
    expected_status: EmergencyStatus,
) -> None:
    """Test turning off emergency switch."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert hass.states.get(entity_id).state == "on"
    mock_client.set_emergency_status.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_client.set_emergency_status.assert_awaited_once_with(expected_status)
    assert hass.states.get(entity_id).state == "off"


@pytest.mark.parametrize(
    "exception",
    [
        ApiError("api error"),
        ApiAuthError(),
        ApiConnectionError("connection failed"),
        ApiSSLError("ssl error"),
    ],
)
async def test_switch_api_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
    exception: Exception,
) -> None:
    """Test switch raises HomeAssistantError on API failure."""
    mock_client.set_emergency_status.side_effect = exception

    with pytest.raises(HomeAssistantError, match="Failed to set emergency status"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: EVACUATION_ENTITY},
            blocking=True,
        )


async def test_switches_are_independent(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test that toggling one switch does not affect the other."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: LOCKDOWN_ENTITY},
        blocking=True,
    )
    assert hass.states.get(LOCKDOWN_ENTITY).state == "on"
    assert hass.states.get(EVACUATION_ENTITY).state == "off"

    mock_client.set_emergency_status.assert_awaited_once_with(
        EmergencyStatus(evacuation=False, lockdown=True)
    )
    mock_client.set_emergency_status.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: EVACUATION_ENTITY},
        blocking=True,
    )
    assert hass.states.get(EVACUATION_ENTITY).state == "on"
    assert hass.states.get(LOCKDOWN_ENTITY).state == "on"

    mock_client.set_emergency_status.assert_awaited_once_with(
        EmergencyStatus(evacuation=True, lockdown=True)
    )


async def test_ws_disconnect_marks_switches_unavailable(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test WebSocket disconnect marks switch entities as unavailable."""
    assert hass.states.get(EVACUATION_ENTITY).state == "off"
    assert hass.states.get(LOCKDOWN_ENTITY).state == "off"

    on_disconnect = _get_on_disconnect(mock_client)
    on_disconnect()
    await hass.async_block_till_done()

    assert hass.states.get(EVACUATION_ENTITY).state == "unavailable"
    assert hass.states.get(LOCKDOWN_ENTITY).state == "unavailable"


async def test_ws_reconnect_restores_switches(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test WebSocket reconnect restores switch availability."""
    on_disconnect = _get_on_disconnect(mock_client)
    on_connect = _get_on_connect(mock_client)

    on_disconnect()
    await hass.async_block_till_done()
    assert hass.states.get(EVACUATION_ENTITY).state == "unavailable"

    on_connect()
    await hass.async_block_till_done()

    assert hass.states.get(EVACUATION_ENTITY).state == "off"
    assert hass.states.get(LOCKDOWN_ENTITY).state == "off"


async def test_ws_setting_update(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test WebSocket setting update refreshes emergency switch state."""
    assert hass.states.get(EVACUATION_ENTITY).state == "off"
    assert hass.states.get(LOCKDOWN_ENTITY).state == "off"

    handlers = _get_ws_handlers(mock_client)
    setting_handler = handlers["access.data.setting.update"]

    await setting_handler(
        SettingUpdate(
            event="access.data.setting.update",
            data=SettingUpdateData(evacuation=True, lockdown=True),
        )
    )
    await hass.async_block_till_done()

    assert hass.states.get(EVACUATION_ENTITY).state == "on"
    assert hass.states.get(LOCKDOWN_ENTITY).state == "on"


async def test_optimistic_update_before_ws_confirmation(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test state is optimistically set immediately, then corrected by WS confirmation.

    Verifies that the optimistic update happens synchronously after the API
    call, without waiting for the WebSocket confirmation message.
    If the WS returns a different value (e.g. hardware rejected the command),
    the state is corrected accordingly.
    """
    assert hass.states.get(EVACUATION_ENTITY).state == "off"

    # Turn on evacuation — state should be optimistically "on" immediately
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: EVACUATION_ENTITY},
        blocking=True,
    )
    assert hass.states.get(EVACUATION_ENTITY).state == "on"

    # Simulate WS confirmation arriving — hardware reported evacuation stayed off
    # (e.g. rejected by the controller), so state should be corrected
    handlers = _get_ws_handlers(mock_client)
    await handlers["access.data.setting.update"](
        SettingUpdate(
            event="access.data.setting.update",
            data=SettingUpdateData(evacuation=False, lockdown=False),
        )
    )
    await hass.async_block_till_done()

    assert hass.states.get(EVACUATION_ENTITY).state == "off"


async def test_no_optimistic_update_when_ws_disconnected(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: MagicMock,
) -> None:
    """Test that optimistic update is skipped when WebSocket is disconnected.

    Prevents async_set_updated_data from flipping last_update_success back
    to True while the coordinator is unavailable due to WS disconnection.
    """
    on_disconnect = _get_on_disconnect(mock_client)
    on_disconnect()
    await hass.async_block_till_done()

    assert hass.states.get(EVACUATION_ENTITY).state == "unavailable"

    # API call succeeds but optimistic update must NOT restore availability
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: EVACUATION_ENTITY},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get(EVACUATION_ENTITY).state == "unavailable"
    assert hass.states.get(LOCKDOWN_ENTITY).state == "unavailable"
