"""Tests for WATERCryst entities."""

from copy import copy
from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.watercryst.coordinator import STATE_POLLING_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import TriggerPollFunc


@pytest.mark.usefixtures("setup_integration")
def test_initialization(
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the creation of the correct device entry."""
    device_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert device_entries == snapshot


@pytest.mark.usefixtures("setup_integration")
async def test_availability(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
    advance_time: TriggerPollFunc,
) -> None:
    """Test entities unavailability when device is offline."""
    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    for online_status in (True, False, True):
        data = copy(mock_api_client.get_state.return_value)
        data.online = online_status
        mock_api_client.get_state.return_value = data

        await advance_time(STATE_POLLING_INTERVAL)

        for entry in entries:
            state = hass.states.get(entry.entity_id)
            assert state is not None
            assert (state.state != STATE_UNAVAILABLE) is online_status
