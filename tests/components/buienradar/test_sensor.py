"""The tests for the Buienradar sensor platform."""

from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.buienradar.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import Platform, UnitOfLength, UnitOfSpeed
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


@pytest.mark.parametrize(
    ("key", "unit", "expected"),
    [
        pytest.param("visibility", UnitOfLength.MILES, 14.54, id="visibility"),
        pytest.param("windspeed", UnitOfSpeed.MILES_PER_HOUR, 9.20, id="windspeed"),
        pytest.param(
            "windspeed_1d", UnitOfSpeed.MILES_PER_HOUR, 8.08, id="windspeed_forecast"
        ),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_buienradar_feeds")
async def test_unit_override(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    key: str,
    unit: str,
    expected: float,
) -> None:
    """Test values are converted once when the unit is overridden."""
    entity_id = entity_registry.async_get_or_create(
        SENSOR_DOMAIN, DOMAIN, f"{TEST_LATITUDE:2.6f}{TEST_LONGITUDE:2.6f}{key}"
    ).entity_id
    entity_registry.async_update_entity_options(
        entity_id, SENSOR_DOMAIN, {"unit_of_measurement": unit}
    )

    await setup_integration(hass)

    state = hass.states.get(entity_id)
    assert float(state.state) == pytest.approx(expected, abs=0.01)
