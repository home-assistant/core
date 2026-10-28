"""Test the Seafile sensor platform."""

from unittest.mock import AsyncMock

from aioseafile import SeafileConnectionError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.seafile.const import DOMAIN
from homeassistant.components.seafile.coordinator import UPDATE_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration
from .conftest import SUBENTRY_ID

LIBRARY_SIZE = "sensor.documents_size"


@pytest.mark.freeze_time("2026-10-15 10:00:00+00:00")
@pytest.mark.usefixtures("mock_seafile_client")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test all entities and the library device."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
    library_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, SUBENTRY_ID), config_entry_id=mock_config_entry.entry_id
    )
    assert library_device.config_subentry_id == SUBENTRY_ID
    for entity in er.async_entries_for_device(entity_registry, library_device.id):
        assert entity.config_subentry_id == SUBENTRY_ID


async def test_library_removed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_seafile_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the sensors of a library that was deleted on the server become unavailable."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(LIBRARY_SIZE).state != STATE_UNAVAILABLE

    mock_seafile_client.get_libraries.return_value = []
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(LIBRARY_SIZE).state == STATE_UNAVAILABLE


async def test_update_failed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_seafile_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the sensors become unavailable when the server can't be reached."""
    await setup_integration(hass, mock_config_entry)

    mock_seafile_client.get_libraries.side_effect = SeafileConnectionError
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(LIBRARY_SIZE).state == STATE_UNAVAILABLE
