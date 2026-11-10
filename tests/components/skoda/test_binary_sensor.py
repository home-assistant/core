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
from skoda_public_api.models.enums import (
    AirConditioningState,
    AuxiliaryHeatingState,
    PlugConnectionState,
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
async def test_only_non_status_binary_sensors_without_status(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test only binary sensors that do not need status data are created without it."""
    await setup_integration(hass, mock_config_entry)

    assert {
        entry.entity_id
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
    } == {"binary_sensor.octavia_auxiliary_heating"}


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
    ("plug_state", "expected_state"),
    [
        (PlugConnectionState.CONNECTED, STATE_ON),
        (PlugConnectionState.DISCONNECTED, STATE_OFF),
        (PlugConnectionState.UNKNOWN, STATE_UNKNOWN),
        (None, STATE_UNKNOWN),
    ],
)
async def test_charging_cable_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
    plug_state: PlugConnectionState | None,
    expected_state: str,
) -> None:
    """Test the charging cable sensor follows the plug connection state."""
    vehicle = mock_skoda_client.get_vehicle.return_value.vehicle
    vehicle.charging.status.plug_connection_state = plug_state

    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get("binary_sensor.enyaq_coupe_charging_cable"))
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("air_conditioning_state", "expected_state"),
    [
        (AirConditioningState.COOLING, STATE_ON),
        (AirConditioningState.HEATING, STATE_ON),
        (AirConditioningState.COMPLETED, STATE_OFF),
        (AirConditioningState.UNKNOWN, STATE_UNKNOWN),
    ],
)
async def test_air_conditioning_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
    air_conditioning_state: AirConditioningState,
    expected_state: str,
) -> None:
    """Test the air conditioning sensor follows the air conditioning state."""
    vehicle = mock_skoda_client.get_vehicle.return_value.vehicle
    vehicle.air_conditioning.state = air_conditioning_state

    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get("binary_sensor.enyaq_coupe_air_conditioning"))
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("auxiliary_heating_state", "expected_state"),
    [
        (AuxiliaryHeatingState.PREHEATING, STATE_ON),
        (AuxiliaryHeatingState.VENTILATION, STATE_ON),
        (AuxiliaryHeatingState.OFF, STATE_OFF),
        (AuxiliaryHeatingState.UNKNOWN, STATE_UNKNOWN),
    ],
)
async def test_auxiliary_heating_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
    auxiliary_heating_state: AuxiliaryHeatingState,
    expected_state: str,
) -> None:
    """Test the auxiliary heating sensor follows the auxiliary heating state."""
    vehicle = mock_skoda_client.get_vehicle.return_value.vehicle
    vehicle.auxiliary_heating.state = auxiliary_heating_state

    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get("binary_sensor.enyaq_coupe_auxiliary_heating"))
    assert state.state == expected_state
