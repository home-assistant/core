"""Tests for the MadVR binary sensor entities."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
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


@pytest.mark.parametrize(
    ("entity_id", "positive_payload", "negative_payload"),
    [
        (
            "binary_sensor.madvr_envy_power_state",
            {"is_on": True},
            {"is_on": False},
        ),
        (
            "binary_sensor.madvr_envy_signal_state",
            {"is_signal": True},
            {"is_signal": False},
        ),
        (
            "binary_sensor.madvr_envy_hdr_flag",
            {"hdr_flag": True},
            {"hdr_flag": False},
        ),
        (
            "binary_sensor.madvr_envy_outgoing_hdr_flag",
            {"outgoing_hdr_flag": True},
            {"outgoing_hdr_flag": False},
        ),
    ],
)
async def test_binary_sensors(
    hass: HomeAssistant,
    mock_madvr_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_id: str,
    positive_payload: dict,
    negative_payload: dict,
) -> None:
    """Test the binary sensors."""
    await setup_integration(hass, mock_config_entry)
    update_callback = get_update_callback(mock_madvr_client)

    # Test positive state
    update_callback(positive_payload)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    # Test negative state
    update_callback(negative_payload)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
