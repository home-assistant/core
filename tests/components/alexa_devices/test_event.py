"""Tests for the Alexa Devices event platform."""

from copy import deepcopy
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .const import TEST_DEVICE_1_SN, TEST_VOCAL_RECORD_EVENT

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "event.echo_test_voice_event"


async def _setup_event_platform(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Set up integration with only the event platform enabled."""
    with patch("homeassistant.components.alexa_devices.PLATFORMS", [Platform.EVENT]):
        await setup_integration(hass, mock_config_entry)


@pytest.mark.usefixtures("mock_amazon_devices_client")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities are registered correctly (snapshot)."""
    await _setup_event_platform(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_initial_state_is_unknown(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Entity state is unknown before any pushed vocal record is received."""
    mock_amazon_devices_client.sync_history_state.return_value = {}
    await _setup_event_platform(hass, mock_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("event_type") is None


@pytest.mark.freeze_time("2025-01-01 00:00:00+00:00")
async def test_history_event_is_fired(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A vocal record pushed by the coordinator triggers a state update."""
    mock_amazon_devices_client.sync_history_state.return_value = {}
    await _setup_event_platform(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    await coordinator.history_state_event_handler(
        {TEST_DEVICE_1_SN: TEST_VOCAL_RECORD_EVENT}
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.attributes == snapshot


async def test_event_attributes_shape(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Fired event carries intent, voice_command and voice_reply attributes."""
    mock_amazon_devices_client.sync_history_state.return_value = {}
    await _setup_event_platform(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    await coordinator.history_state_event_handler(
        {TEST_DEVICE_1_SN: TEST_VOCAL_RECORD_EVENT}
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.attributes.get("event_type") == "triggered"
    assert state.attributes.get("intent") == TEST_VOCAL_RECORD_EVENT.intent
    assert state.attributes.get("voice_command") == TEST_VOCAL_RECORD_EVENT.title
    assert state.attributes.get("voice_reply") == TEST_VOCAL_RECORD_EVENT.sub_title


async def test_duplicate_event_is_not_refired(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A second push with the same timestamp must not change the entity state."""
    mock_amazon_devices_client.sync_history_state.return_value = {}
    await _setup_event_platform(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    await coordinator.history_state_event_handler(
        {TEST_DEVICE_1_SN: TEST_VOCAL_RECORD_EVENT}
    )
    await hass.async_block_till_done()

    first_last_updated = hass.states.get(ENTITY_ID).last_updated

    freezer.tick(1)

    await coordinator.history_state_event_handler(
        {TEST_DEVICE_1_SN: TEST_VOCAL_RECORD_EVENT}
    )
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).last_updated == first_last_updated


async def test_older_event_is_discarded(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A record with an older timestamp than the last seen one is ignored."""
    mock_amazon_devices_client.sync_history_state.return_value = {}
    await _setup_event_platform(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    await coordinator.history_state_event_handler(
        {TEST_DEVICE_1_SN: TEST_VOCAL_RECORD_EVENT}
    )
    await hass.async_block_till_done()

    first_last_updated = hass.states.get(ENTITY_ID).last_updated

    freezer.tick(1)

    stale_record = deepcopy(TEST_VOCAL_RECORD_EVENT)
    stale_record.timestamp = TEST_VOCAL_RECORD_EVENT.timestamp - 1

    await coordinator.history_state_event_handler({TEST_DEVICE_1_SN: stale_record})
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).last_updated == first_last_updated


async def test_newer_event_after_duplicate_is_fired(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """After a duplicate is discarded, a record with a newer timestamp does fire."""
    mock_amazon_devices_client.sync_history_state.return_value = {}
    await _setup_event_platform(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    await coordinator.history_state_event_handler(
        {TEST_DEVICE_1_SN: TEST_VOCAL_RECORD_EVENT}
    )
    await hass.async_block_till_done()

    first_last_updated = hass.states.get(ENTITY_ID).last_updated

    freezer.tick(1)

    newer_record = deepcopy(TEST_VOCAL_RECORD_EVENT)
    newer_record.timestamp = TEST_VOCAL_RECORD_EVENT.timestamp + 1

    await coordinator.history_state_event_handler({TEST_DEVICE_1_SN: newer_record})
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).last_updated != first_last_updated


async def test_no_vocal_record_skips_event_trigger(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """An empty handler payload leaves the entity in STATE_UNKNOWN."""
    mock_amazon_devices_client.sync_history_state.return_value = {}
    await _setup_event_platform(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    await coordinator.history_state_event_handler({})
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("event_type") is None


async def test_wrong_device_serial_is_ignored(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A vocal record for a different serial number does not affect this entity."""
    mock_amazon_devices_client.sync_history_state.return_value = {}
    await _setup_event_platform(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data
    await coordinator.history_state_event_handler(
        {"DIFFERENT_SERIAL_NUMBER": TEST_VOCAL_RECORD_EVENT}
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNKNOWN


async def test_multiple_devices_only_update_own_entity(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A push containing records for multiple devices only fires for the matching one."""
    mock_amazon_devices_client.sync_history_state.return_value = {}
    await _setup_event_platform(hass, mock_config_entry)

    other_record = deepcopy(TEST_VOCAL_RECORD_EVENT)
    other_record.timestamp = TEST_VOCAL_RECORD_EVENT.timestamp + 999

    coordinator = mock_config_entry.runtime_data
    await coordinator.history_state_event_handler(
        {
            TEST_DEVICE_1_SN: TEST_VOCAL_RECORD_EVENT,
            "OTHER_DEVICE_SN": other_record,
        }
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state != STATE_UNKNOWN
    assert state.attributes.get("event_type") == "triggered"
