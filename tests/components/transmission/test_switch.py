"""Tests for the Transmission switch platform."""

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
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


async def test_switches(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_transmission_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the switch entities."""
    with patch("homeassistant.components.transmission.PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("service", "api_method"),
    [
        (SERVICE_TURN_ON, "start_all"),
        (SERVICE_TURN_OFF, "stop_torrent"),
    ],
)
async def test_on_off_switch_without_torrents(
    hass: HomeAssistant,
    mock_transmission_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_torrent,
    service: str,
    api_method: str,
) -> None:
    """Test on/off switch."""
    client = mock_transmission_client.return_value
    client.get_torrents.return_value = []

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: "switch.transmission_switch"},
        blocking=True,
    )

    getattr(client, api_method).assert_not_called()


@pytest.mark.parametrize(
    ("service", "api_method"),
    [
        (SERVICE_TURN_ON, "start_all"),
        (SERVICE_TURN_OFF, "stop_torrent"),
    ],
)
async def test_on_off_switch_with_torrents(
    hass: HomeAssistant,
    mock_transmission_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_torrent,
    service: str,
    api_method: str,
) -> None:
    """Test on/off switch."""
    client = mock_transmission_client.return_value
    client.get_torrents.return_value = [mock_torrent()]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: "switch.transmission_switch"},
        blocking=True,
    )

    getattr(client, api_method).assert_called_once()


@pytest.mark.parametrize(
    ("service", "alt_speed_enabled"),
    [
        (SERVICE_TURN_ON, True),
        (SERVICE_TURN_OFF, False),
    ],
)
async def test_turtle_mode_switch(
    hass: HomeAssistant,
    mock_transmission_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    alt_speed_enabled: bool,
) -> None:
    """Test turtle mode switch."""
    client = mock_transmission_client.return_value

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: "switch.transmission_turtle_mode"},
        blocking=True,
    )

    client.set_session.assert_called_once_with(alt_speed_enabled=alt_speed_enabled)


async def test_turtle_mode_optimistic_state(
    hass: HomeAssistant,
    mock_transmission_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test toggling updates optimistic state correctly.

    When users toggle the switch multiple times in quick succession,
    each action should update the optimistic state immediately.
    This test verifies that rapid ON→OFF→ON toggles work correctly
    with the timestamp-based optimistic state mechanism.
    """

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("switch.transmission_turtle_mode")
    assert state.state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.transmission_turtle_mode"},
        blocking=True,
    )
    state = hass.states.get("switch.transmission_turtle_mode")
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.transmission_turtle_mode"},
        blocking=True,
    )
    state = hass.states.get("switch.transmission_turtle_mode")
    assert state.state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.transmission_turtle_mode"},
        blocking=True,
    )
    state = hass.states.get("switch.transmission_turtle_mode")
    assert state.state == STATE_ON
