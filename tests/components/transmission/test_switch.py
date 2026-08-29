"""Tests for the Transmission switch platform."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from transmission_rpc.session import Session

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
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
    ("service", "alt_speed_enabled", "expected_state"),
    [
        (SERVICE_TURN_ON, True, "on"),
        (SERVICE_TURN_OFF, False, "off"),
    ],
)
async def test_turtle_mode_switch(
    hass: HomeAssistant,
    mock_transmission_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    alt_speed_enabled: bool,
    expected_state: str,
) -> None:
    """Test turtle mode switch."""
    client = mock_transmission_client.return_value

    current_alt_speed = not alt_speed_enabled

    def set_session_side_effect(**kwargs):
        nonlocal current_alt_speed
        if "alt_speed_enabled" in kwargs:
            current_alt_speed = kwargs["alt_speed_enabled"]

    client.set_session.side_effect = set_session_side_effect
    client.get_session.side_effect = lambda: Session(
        fields={"alt-speed-enabled": current_alt_speed}
    )

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

    state = hass.states.get("switch.transmission_turtle_mode")
    assert state is not None
    assert state.state == expected_state
