"""Test the Teslemetry device tracker platform."""

from unittest.mock import AsyncMock

import pytest
from syrupy.assertion import SnapshotAssertion
from teslemetry_stream.const import Signal

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import assert_entities, assert_entities_alt, setup_platform
from .const import METADATA_NOSCOPE, VEHICLE_DATA_ALT


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_device_tracker(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_legacy: AsyncMock,
) -> None:
    """Tests that the device tracker entities are correct."""

    entry = await setup_platform(hass, [Platform.DEVICE_TRACKER])
    assert_entities(hass, entry.entry_id, entity_registry, snapshot)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_device_tracker_alt(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_vehicle_data: AsyncMock,
    mock_legacy: AsyncMock,
) -> None:
    """Tests that the device tracker entities are correct."""

    mock_vehicle_data.return_value = VEHICLE_DATA_ALT
    entry = await setup_platform(hass, [Platform.DEVICE_TRACKER])
    assert_entities_alt(hass, entry.entry_id, entity_registry, snapshot)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_device_tracker_noscope(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_metadata: AsyncMock,
    mock_vehicle_data: AsyncMock,
    mock_legacy: AsyncMock,
) -> None:
    """Tests that the device tracker entities are correct."""

    mock_metadata.return_value = METADATA_NOSCOPE
    entry = await setup_platform(hass, [Platform.DEVICE_TRACKER])
    entity_entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    assert len(entity_entries) == 0


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_device_tracker_streaming(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_vehicle_data: AsyncMock,
    mock_add_listener: AsyncMock,
) -> None:
    """Tests that the device tracker entities with streaming are correct."""

    entry = await setup_platform(hass, [Platform.DEVICE_TRACKER])

    # Stream update
    mock_add_listener.send(
        {
            "vin": VEHICLE_DATA_ALT["response"]["vin"],
            "data": {
                Signal.LOCATION: {
                    "latitude": 1.0,
                    "longitude": 2.0,
                },
                Signal.DESTINATION_LOCATION: {
                    "latitude": 3.0,
                    "longitude": 4.0,
                },
                Signal.DESTINATION_NAME: "Home",
                Signal.ORIGIN_LOCATION: None,
            },
            "createdAt": "2024-10-04T10:45:17.537Z",
        }
    )
    await hass.async_block_till_done()

    # Assert the entities restored their values
    for entity_id in (
        "device_tracker.test_location",
        "device_tracker.test_route",
        "device_tracker.test_origin",
    ):
        state = hass.states.get(entity_id)
        assert state.state == snapshot(name=f"{entity_id}-state")

    # Reload the entry
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    # Assert the entities restored their values
    for entity_id in (
        "device_tracker.test_location",
        "device_tracker.test_route",
        "device_tracker.test_origin",
    ):
        state = hass.states.get(entity_id)
        assert state.state == snapshot(name=f"{entity_id}-restore")
