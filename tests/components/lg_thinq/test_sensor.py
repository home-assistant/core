"""Tests for the LG Thinq sensor platform."""

from datetime import UTC, datetime, time, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lg_thinq.const import DOMAIN
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from . import setup_integration

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed_exact,
    async_load_json_object_fixture,
    snapshot_platform,
)


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
@pytest.mark.freeze_time(datetime(2024, 10, 9, 10, 0, tzinfo=UTC))
async def test_update_energy_entity(
    hass: HomeAssistant,
    devices: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_thinq_api: AsyncMock,
    device_fixture: str,
    energy_fixture: str,
    energy_usage: int,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test update energy entity."""
    with patch(
        "homeassistant.components.lg_thinq.sensor.random.randint", return_value=1
    ):
        await setup_integration(hass, mock_config_entry)

    entity_id = f"sensor.test_{device_fixture}_energy_{energy_fixture}"
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNKNOWN

    mock_thinq_api.async_get_device_energy_usage.return_value = (
        await async_load_json_object_fixture(
            hass, f"{device_fixture}/energy_{energy_fixture}.json", DOMAIN
        )
    )
    async_fire_time_changed_exact(
        hass, datetime.combine(utcnow() + timedelta(days=1), time(1, 1))
    )
    await hass.async_block_till_done()

    entity_registry.async_update_entity(entity_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert float(state.state) == energy_usage
