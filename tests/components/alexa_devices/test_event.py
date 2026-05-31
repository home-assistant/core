"""Tests for the Alexa Devices event platform."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .const import TEST_DEVICE_1_SN, TEST_VOCAL_RECORD_EVENT

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "event.echo_test_voice_event"


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.alexa_devices.PLATFORMS", [Platform.EVENT]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.freeze_time("2025-01-01 00:00:00+00:00")
async def test_history_event_is_fired(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test history updates trigger voice event entity state updates."""
    with patch("homeassistant.components.alexa_devices.PLATFORMS", [Platform.EVENT]):
        await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    await coordinator.history_state_event_handler(
        {TEST_DEVICE_1_SN: TEST_VOCAL_RECORD_EVENT}
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.attributes == snapshot


async def test_no_vocal_record_skips_event_trigger(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a coordinator update with no vocal record skips event trigger."""
    mock_amazon_devices_client.sync_history_state.return_value = {}
    with patch("homeassistant.components.alexa_devices.PLATFORMS", [Platform.EVENT]):
        await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    await coordinator.history_state_event_handler({})
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("event_type") is None
