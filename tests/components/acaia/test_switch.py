"""Tests for the acaia switch."""

import asyncio
from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID = "switch.kitchen_lunar_ddeeff_keep_connected"


async def test_switch(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_scale: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the acaia switch."""

    with patch("homeassistant.components.acaia.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_switch_defaults_to_on(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the switch is on by default, preserving the always-connected behavior."""

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_ON


async def test_turning_off_disconnects_scale(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning the switch off disconnects the scale."""

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    mock_scale.disconnect.assert_called_once()
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_OFF


async def test_turning_on_reconnects_scale(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning the switch back on re-establishes the connection."""

    await setup_integration(hass, mock_config_entry)
    mock_scale.connect.reset_mock()
    mock_scale.connected = False

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    mock_scale.connect.assert_called_once()
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_ON


async def test_switch_state_survives_reload_without_reconnecting(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the switch restores its last state across a config entry reload.

    The preference is read from config entry options during coordinator
    init, before the first refresh runs, so a restored "off" state must not
    cause the coordinator to reconnect the scale on that first refresh.
    """

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    mock_scale.connected = False
    mock_scale.connect.reset_mock()

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_scale.connect.assert_not_called()
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_OFF


async def test_switch_available_while_scale_disconnected(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the switch stays available even while the scale is disconnected.

    Unlike other entities, this one has to remain usable while disconnected
    since it is the control that reconnects the scale.
    """

    await setup_integration(hass, mock_config_entry)
    mock_scale.connected = False

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state != "unavailable"


async def test_turning_on_while_connected_does_not_reconnect(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test turning the switch on while already connected keeps the connection."""

    await setup_integration(hass, mock_config_entry)
    mock_scale.connect.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    mock_scale.connect.assert_not_called()


async def test_turning_off_during_pending_connect_disconnects(
    hass: HomeAssistant,
    mock_scale: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test turning off while a reconnect is in flight leaves the scale disconnected."""

    await setup_integration(hass, mock_config_entry)
    mock_scale.connected = False
    connect_started = asyncio.Event()
    release_connect = asyncio.Event()

    async def _blocked_connect(**kwargs: bool) -> None:
        connect_started.set()
        await release_connect.wait()
        mock_scale.connected = True

    mock_scale.connect.side_effect = _blocked_connect

    freezer.tick(timedelta(seconds=15))
    async_fire_time_changed(hass)
    await connect_started.wait()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_scale.disconnect.assert_not_called()

    release_connect.set()
    await hass.async_block_till_done()

    mock_scale.disconnect.assert_called_once()
    assert mock_scale.heartbeat_task is None
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_OFF
