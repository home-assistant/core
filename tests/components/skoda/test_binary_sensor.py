"""Test the Škoda binary sensor platform."""

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
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Only set up the binary sensor platform."""
    with patch("homeassistant.components.skoda._PLATFORMS", [Platform.BINARY_SENSOR]):
        yield


@pytest.mark.parametrize(
    "vehicle_fixture", ["vehicle_electric.json", "vehicle_hybrid.json"]
)
async def test_binary_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Škoda binary sensor entities against a snapshot."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("vehicle_fixture", ["vehicle_combustion.json"])
async def test_no_binary_sensors_without_status(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test no binary sensors are created for a vehicle without status data."""
    await setup_integration(hass, mock_config_entry)

    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )


@pytest.mark.parametrize(
    ("reliable_lock_status", "locked", "expected_state"),
    [
        pytest.param("UNLOCKED", "YES", STATE_ON, id="reliable_unlocked"),
        pytest.param("LOCKED", "NO", STATE_OFF, id="reliable_locked"),
        pytest.param("UNKNOWN", "YES", STATE_UNKNOWN, id="reliable_unknown"),
    ],
)
async def test_lock_prefers_reliable_lock_status(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
    reliable_lock_status: str,
    locked: str,
    expected_state: str,
) -> None:
    """Test the lock sensor uses the reliable lock status over the fallback."""
    vehicle = await async_load_json_object_fixture(
        hass, "vehicle_electric.json", DOMAIN
    )
    overall = vehicle["vehicle"]["status"]["overall"]
    overall["reliableLockStatus"] = reliable_lock_status
    overall["locked"] = locked
    mock_skoda_client.get_vehicle.return_value = VehicleResponse.model_validate(vehicle)

    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get("binary_sensor.enyaq_coupe_lock"))
    assert state.state == expected_state


async def test_binary_sensor_unknown_when_status_missing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a binary sensor reports unknown when a later update lacks status data."""
    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get("binary_sensor.enyaq_coupe_doors"))
    assert state.state == STATE_OFF

    mock_skoda_client.get_vehicle.return_value = VehicleResponse.model_validate(
        await async_load_json_object_fixture(hass, "vehicle_unavailable.json", DOMAIN)
    )
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get("binary_sensor.enyaq_coupe_doors"))
    assert state.state == STATE_UNKNOWN
