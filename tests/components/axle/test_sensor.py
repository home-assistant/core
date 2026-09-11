"""Test event metadata and coordinator lifecycle."""

from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock

from aioaxlevpp import (
    AxleAuthenticationError,
    AxleConnectionError,
    AxleError,
    GridEvent,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Load the integration."""
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_sensor_snapshot(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the registered sensors and their state attributes."""
    await setup(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "value", "key"),
    [
        ("sensor.axle_energy_import_export", "export", "import_export"),
        ("sensor.axle_energy_event_start", "2026-09-11T17:00:00+00:00", "start"),
        ("sensor.axle_energy_event_end", "2026-09-11T18:00:00+00:00", "end"),
    ],
)
async def test_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    entity_id: str,
    value: str,
    key: str,
) -> None:
    """Expose the three event inputs with persistent identities."""
    await setup(hass, mock_config_entry)
    assert hass.states.get(entity_id).state == value
    registered = entity_registry.async_get(entity_id)
    assert registered is not None
    assert registered.config_entry_id == mock_config_entry.entry_id
    assert registered.unique_id == f"{mock_config_entry.entry_id}_{key}"
    assert (
        len(
            er.async_entries_for_config_entry(
                entity_registry, mock_config_entry.entry_id
            )
        )
        == 3
    )


async def test_no_event(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: AsyncMock
) -> None:
    """An empty schedule is unknown, not a failed connection."""
    mock_client.get_event.return_value = None
    await setup(hass, mock_config_entry)
    assert hass.states.get("sensor.axle_energy_import_export").state == "unknown"


async def test_opted_out(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    mock_event: GridEvent,
) -> None:
    """Exclude an event the household has opted out of."""
    mock_client.get_event.return_value = replace(mock_event, opted_out=True)
    await setup(hass, mock_config_entry)
    assert hass.states.get("sensor.axle_energy_import_export").state == "unknown"


@pytest.mark.parametrize(
    "error", [AxleAuthenticationError(), AxleConnectionError(), AxleError()]
)
async def test_recovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    error: Exception,
) -> None:
    """Recover from a failed request without confusing it with no event."""
    await setup(hass, mock_config_entry)
    mock_client.get_event.side_effect = error
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.axle_energy_import_export").state == "unavailable"
    mock_client.get_event.side_effect = None
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.axle_energy_import_export").state == "export"


async def test_polling(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    mock_event: GridEvent,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Poll at ten minutes and publish revised direction."""
    await setup(hass, mock_config_entry)
    mock_client.get_event.reset_mock()
    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_client.get_event.assert_not_called()
    mock_client.get_event.return_value = replace(mock_event, direction="import")
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    mock_client.get_event.assert_awaited_once()
    assert hass.states.get("sensor.axle_energy_import_export").state == "import"
