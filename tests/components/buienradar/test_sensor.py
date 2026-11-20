"""The tests for the Buienradar sensor platform."""

from datetime import timedelta
from unittest.mock import patch

from buienradar.constants import MESSAGE, SUCCESS
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.buienradar.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import TEST_CFG_DATA, TEST_LATITUDE, TEST_LONGITUDE, setup_integration

CONDITIONS = {"stationname": "Eindhoven (6370)", "temperature": "8.2"}


@pytest.mark.usefixtures("mock_buienradar_feeds")
async def test_smoke_test_setup_component(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Smoke test for successfully set-up with default config."""
    mock_entry = MockConfigEntry(domain=DOMAIN, unique_id="TEST_ID", data=TEST_CFG_DATA)
    mock_entry.add_to_hass(hass)

    entity_ids = {
        cond: entity_registry.async_get_or_create(
            domain="sensor",
            platform="buienradar",
            unique_id=f"{TEST_LATITUDE:2.6f}{TEST_LONGITUDE:2.6f}{cond}",
            config_entry=mock_entry,
            original_name=f"Buienradar {cond}",
        ).entity_id
        for cond in CONDITIONS
    }

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    for cond, value in CONDITIONS.items():
        assert hass.states.get(entity_ids[cond]).state == value


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_buienradar_feeds")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all sensors."""
    with patch("homeassistant.components.buienradar.PLATFORMS", [Platform.SENSOR]):
        entry = await setup_integration(hass)

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_buienradar_feeds")
async def test_sensor_unavailable_and_recovery(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensors are unavailable after a failed update and recover."""
    with patch("homeassistant.components.buienradar.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass)
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{TEST_LATITUDE:2.6f}{TEST_LONGITUDE:2.6f}temperature"
    )
    assert entity_id
    assert hass.states.get(entity_id).state == "8.2"

    with patch(
        "homeassistant.components.buienradar.util.parse_data",
        return_value={SUCCESS: False, MESSAGE: "no data"},
    ):
        freezer.tick(timedelta(minutes=10))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # A failed update is retried two minutes later, with the same measurement.
    freezer.tick(timedelta(minutes=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(entity_id).state == "8.2"
