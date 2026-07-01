"""Tests for the WattWächter Plus sensor platform."""

from __future__ import annotations

from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.wattwaechter.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_DEVICE_ID, MOCK_METER_DATA_MINIMAL

from tests.common import MockConfigEntry, snapshot_platform


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """Test all sensor entities created from a full OBIS payload."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_minimal_meter_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that only reported OBIS codes create sensors (dynamic)."""
    mock_client.meter_data.return_value = MOCK_METER_DATA_MINIMAL

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    def _get_entity_id(obis_code: str) -> str | None:
        return entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{MOCK_DEVICE_ID}_{obis_code}"
        )

    # Sensors for reported OBIS codes should exist
    assert _get_entity_id("1.8.0") is not None
    assert _get_entity_id("16.7.0") is not None

    # Sensors for unreported OBIS codes should NOT exist
    assert _get_entity_id("2.8.0") is None
    assert _get_entity_id("32.7.0") is None
    assert _get_entity_id("31.7.0") is None
