"""Tests for the LG Thinq sensor platform."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize("device_fixture", ["air_conditioner"])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.freeze_time(datetime(2024, 10, 10, tzinfo=UTC))
async def test_sensor_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    hass.config.time_zone = "UTC"
    with patch("homeassistant.components.lg_thinq.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("device_fixture", "energy_fixture", "energy_usage"),
    [
        ("air_conditioner", "yesterday", 100),
        ("air_conditioner", "this_month", 500),
        ("air_conditioner", "last_month", 700),
    ],
)
async def test_energy_entity(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_energy_usage: AsyncMock,
    mock_config_entry: MockConfigEntry,
    energy_fixture: str,
    energy_usage: int,
) -> None:
    """Test energy entity."""
    await setup_integration(hass, mock_config_entry)

    assert (
        state := hass.states.get(f"sensor.test_air_conditioner_energy_{energy_fixture}")
    )
    assert float(state.state) == energy_usage
