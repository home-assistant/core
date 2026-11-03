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
async def test_no_status_binary_sensors_without_status(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test no status binary sensors are created for a vehicle without status data."""
    await setup_integration(hass, mock_config_entry)

    assert [
        entry.entity_id
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
    ] == ["binary_sensor.octavia_auxiliary_heating"]


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


@pytest.mark.parametrize(
    ("entity_id", "initial_state"),
    [
        ("binary_sensor.enyaq_coupe_doors", STATE_OFF),
        ("binary_sensor.enyaq_coupe_charging_cable", STATE_ON),
        ("binary_sensor.enyaq_coupe_air_conditioning", STATE_OFF),
        ("binary_sensor.enyaq_coupe_auxiliary_heating", STATE_OFF),
    ],
)
async def test_binary_sensor_unknown_when_data_missing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    entity_id: str,
    initial_state: str,
) -> None:
    """Test a binary sensor reports unknown when a later update lacks its data."""
    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(entity_id))
    assert state.state == initial_state

    mock_skoda_client.get_vehicle.return_value = VehicleResponse.model_validate(
        await async_load_json_object_fixture(hass, "vehicle_unavailable.json", DOMAIN)
    )
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("block", "field", "value", "entity_id", "expected_state"),
    [
        pytest.param(
            "charging",
            "plugConnectionState",
            "DISCONNECTED",
            "binary_sensor.enyaq_coupe_charging_cable",
            STATE_OFF,
            id="cable_disconnected",
        ),
        pytest.param(
            "charging",
            "plugConnectionState",
            "UNKNOWN",
            "binary_sensor.enyaq_coupe_charging_cable",
            STATE_UNKNOWN,
            id="cable_unknown",
        ),
        pytest.param(
            "charging",
            "plugConnectionState",
            None,
            "binary_sensor.enyaq_coupe_charging_cable",
            STATE_UNKNOWN,
            id="cable_not_reported",
        ),
        pytest.param(
            "airConditioning",
            "state",
            "COOLING",
            "binary_sensor.enyaq_coupe_air_conditioning",
            STATE_ON,
            id="air_conditioning_cooling",
        ),
        pytest.param(
            "airConditioning",
            "state",
            "COMPLETED",
            "binary_sensor.enyaq_coupe_air_conditioning",
            STATE_OFF,
            id="air_conditioning_completed",
        ),
        pytest.param(
            "airConditioning",
            "state",
            "UNKNOWN",
            "binary_sensor.enyaq_coupe_air_conditioning",
            STATE_UNKNOWN,
            id="air_conditioning_unknown",
        ),
        pytest.param(
            "auxiliaryHeating",
            "state",
            "PREHEATING",
            "binary_sensor.enyaq_coupe_auxiliary_heating",
            STATE_ON,
            id="auxiliary_heating_preheating",
        ),
        pytest.param(
            "auxiliaryHeating",
            "state",
            "UNKNOWN",
            "binary_sensor.enyaq_coupe_auxiliary_heating",
            STATE_UNKNOWN,
            id="auxiliary_heating_unknown",
        ),
    ],
)
async def test_running_and_plug_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
    block: str,
    field: str,
    value: str | None,
    entity_id: str,
    expected_state: str,
) -> None:
    """Test the charging cable and running binary sensors map the vehicle states."""
    vehicle = await async_load_json_object_fixture(
        hass, "vehicle_electric.json", DOMAIN
    )
    data = vehicle["vehicle"][block]
    if block == "charging":
        data = data["status"]
    if value is None:
        data.pop(field)
    else:
        data[field] = value
    mock_skoda_client.get_vehicle.return_value = VehicleResponse.model_validate(vehicle)

    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(entity_id))
    assert state.state == expected_state
