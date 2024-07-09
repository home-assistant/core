"""Tests for the MadVR binary sensor entities."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from syrupy import SnapshotAssertion

from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er

from . import setup_integration
from .conftest import get_update_callback

from tests.common import MockConfigEntry, snapshot_platform


async def test_binary_sensor_setup(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup of the binary sensor entities."""
    with patch("homeassistant.components.madvr.PLATFORMS", [Platform.BINARY_SENSOR]):
        await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_power_state_binary_sensor(
    hass: HomeAssistant,
    mock_madvr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the power state binary sensor."""
    await setup_integration(hass, mock_config_entry)
    entity_id = "binary_sensor.madvr_envy_power_state"

    state = hass.states.get(entity_id)
    # this gets the power state from the client
    assert state.state == STATE_ON


async def test_signal_state_binary_sensor(
    hass: HomeAssistant,
    mock_madvr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the signal state binary sensor."""
    await setup_integration(hass, mock_config_entry)
    entity_id = "binary_sensor.madvr_envy_signal_state"

    # retrieve the handle_update function from mock
    update_callback = get_update_callback(mock_madvr_client)
    # simulate the coordinator receiving data from callback
    update_callback({"is_signal": False, "fake_key": "other_value"})

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    # Test signal detected
    update_callback({"is_signal": True})
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON


async def test_hdr_flag_binary_sensor(
    hass: HomeAssistant,
    mock_madvr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the HDR flag binary sensor."""
    await setup_integration(hass, mock_config_entry)
    entity_id = "binary_sensor.madvr_envy_hdr_flag"

    # Test initial state (assuming no HDR)
    update_callback = get_update_callback(mock_madvr_client)
    update_callback({"hdr_flag": False})

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    # Test HDR detected
    update_callback({"hdr_flag": True})

    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON


async def test_outgoing_hdr_flag_binary_sensor(
    hass: HomeAssistant,
    mock_madvr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the outgoing HDR flag binary sensor."""
    await setup_integration(hass, mock_config_entry)
    entity_id = "binary_sensor.madvr_envy_outgoing_hdr_flag"

    # Test initial state (assuming no outgoing HDR)
    update_callback = get_update_callback(mock_madvr_client)
    update_callback({"outgoing_hdr_flag": False})

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    # Test outgoing HDR detected
    update_callback({"outgoing_hdr_flag": True})

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
