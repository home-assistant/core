"""Test the Škoda sensor platform."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_load_json_object_fixture,
    snapshot_platform,
)
from skoda_public_api.models.vehicle import VehicleResponse
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.skoda.const import DOMAIN
from homeassistant.components.skoda.coordinator import UPDATE_INTERVAL
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Only set up the sensor platform."""
    with patch("homeassistant.components.skoda._PLATFORMS", [Platform.SENSOR]):
        yield


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    "vehicle_fixture",
    [
        "vehicle_electric.json",
        "vehicle_hybrid.json",
        "vehicle_combustion.json",
        "vehicle_incomplete.json",
        "vehicle_unavailable.json",
    ],
)
async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Škoda sensor entities against a snapshot."""
    freezer.move_to("2024-01-10T12:00:00+00:00")

    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("vehicle_fixture", ["vehicle_hybrid.json"])
async def test_sensor_unknown_when_data_becomes_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a sensor reports unknown when a later update lacks its data."""
    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get("sensor.superb_fuel_level"))
    assert state.state == "42"

    mock_skoda_client.get_vehicle.return_value = VehicleResponse.model_validate(
        await async_load_json_object_fixture(hass, "vehicle_unavailable.json", DOMAIN)
    )
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get("sensor.superb_fuel_level"))
    assert state.state == STATE_UNKNOWN
