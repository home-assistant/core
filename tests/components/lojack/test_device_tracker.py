"""Tests for the LoJack device tracker platform."""

from unittest.mock import AsyncMock, patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.device_tracker import SourceType
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .const import (
    TEST_DEVICE_ID,
    TEST_LATITUDE,
    TEST_LONGITUDE,
)

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "device_tracker.2021_honda_accord"


async def test_all_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all device tracker entities are created."""
    with patch("homeassistant.components.lojack.PLATFORMS", [Platform.DEVICE_TRACKER]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_device_tracker_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: AsyncMock,
) -> None:
    """Test device tracker state and attributes."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "not_home"

    # Check location attributes
    attrs = state.attributes
    assert attrs["latitude"] == TEST_LATITUDE
    assert attrs["longitude"] == TEST_LONGITUDE
    assert attrs["gps_accuracy"] == 10
    assert attrs["source_type"] == SourceType.GPS


async def test_device_tracker_no_location(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: AsyncMock,
) -> None:
    """Test device tracker when API returns None for location."""
    mock_device.get_location = AsyncMock(return_value=None)
    # Clear year/make/model to exercise fallback to device.name
    mock_device.year = None
    mock_device.make = None
    mock_device.model = None

    client = AsyncMock()
    client.user_id = "user123"
    client.list_devices = AsyncMock(return_value=[mock_device])
    client.close = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "homeassistant.components.lojack.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
            return_value=client,
        ),
    ):
        await setup_integration(hass, mock_config_entry)

    # Without year/make/model, device name falls back to device.name
    state = hass.states.get("device_tracker.my_car")
    assert state is not None
    # No location data
    assert state.attributes.get("latitude") is None
    assert state.attributes.get("longitude") is None


async def test_device_tracker_unique_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that device tracker has correct unique ID."""
    await setup_integration(hass, mock_config_entry)

    entity_entry = entity_registry.async_get(ENTITY_ID)
    assert entity_entry is not None
    assert entity_entry.unique_id == TEST_DEVICE_ID
