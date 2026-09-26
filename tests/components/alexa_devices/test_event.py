"""Tests for the Alexa Devices event platform."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.alexa_devices.const import DOMAIN
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import assert_device_removed_and_readded, setup_integration
from .const import (
    TEST_DEVICE_1,
    TEST_DEVICE_1_SN,
    TEST_DEVICE_2,
    TEST_DEVICE_2_SN,
    TEST_VOCAL_RECORD_EVENT,
)

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


async def test_device_removed_and_readded(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test entities are recreated when a device is removed and re-added."""
    await assert_device_removed_and_readded(
        hass,
        freezer,
        mock_amazon_devices_client,
        mock_config_entry,
        entity_id="event.echo_test_2_voice_event",
        devices_with={TEST_DEVICE_1_SN: TEST_DEVICE_1, TEST_DEVICE_2_SN: TEST_DEVICE_2},
        devices_without={TEST_DEVICE_1_SN: TEST_DEVICE_1},
    )


async def test_voice_event_not_created_for_unsupported_device(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test voice event entity is not created for devices without voice control support."""
    mock_amazon_devices_client.get_devices_data.return_value[
        TEST_DEVICE_1_SN
    ].voice_control_supported = False

    with patch("homeassistant.components.alexa_devices.PLATFORMS", [Platform.EVENT]):
        await setup_integration(hass, mock_config_entry)

    assert not hass.states.get(ENTITY_ID)


async def test_voice_event_removed_for_unsupported_device(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test voice event entity is removed for devices without voice control support."""
    mock_config_entry.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, TEST_DEVICE_1_SN)},
        name="Echo Test",
        manufacturer="Amazon",
        model="Echo Dot",
    )

    entity = entity_registry.async_get_or_create(
        Platform.EVENT,
        DOMAIN,
        unique_id=f"{TEST_DEVICE_1_SN}-voice_event",
        device_id=device.id,
        config_entry=mock_config_entry,
        has_entity_name=True,
    )

    mock_amazon_devices_client.get_devices_data.return_value[
        TEST_DEVICE_1_SN
    ].voice_control_supported = False

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.states.get(entity.entity_id)
    assert entity_registry.async_get(entity.entity_id) is None
