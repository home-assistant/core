"""Test the Škoda climate platform."""

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
from skoda_public_api.api_layer.exceptions import OpenApiError
from skoda_public_api.models.enums import AirConditioningState
from skoda_public_api.models.vehicle import VehicleResponse
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    HVACAction,
    HVACMode,
)
from homeassistant.components.skoda.const import DOMAIN
from homeassistant.components.skoda.coordinator import UPDATE_INTERVAL
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import VIN

ENYAQ = "climate.enyaq_coupe_air_conditioning"
SUPERB = "climate.superb_air_conditioning"


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Only set up the climate platform."""
    with patch("homeassistant.components.skoda._PLATFORMS", [Platform.CLIMATE]):
        yield


@pytest.mark.usefixtures("mock_skoda_client")
@pytest.mark.parametrize(
    "vehicle_fixture",
    ["vehicle_electric.json", "vehicle_hybrid.json", "vehicle_unavailable.json"],
)
async def test_climate(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Škoda climate entities against a snapshot."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_skoda_client")
@pytest.mark.parametrize("vehicle_fixture", ["vehicle_combustion.json"])
async def test_no_climate_without_air_conditioning(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test no climate entity is created for a vehicle without air conditioning."""
    await setup_integration(hass, mock_config_entry)

    assert not hass.states.async_entity_ids(CLIMATE_DOMAIN)


async def test_no_climate_without_operation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
) -> None:
    """Test no climate entity is created when the vehicle cannot start it remotely."""
    vehicle = await async_load_json_object_fixture(
        hass, "vehicle_electric.json", DOMAIN
    )
    vehicle["vehicle"]["operations"] = [{"name": "startCharging"}]
    mock_skoda_client.get_vehicle.return_value = VehicleResponse.model_validate(vehicle)

    await setup_integration(hass, mock_config_entry)

    assert not hass.states.async_entity_ids(CLIMATE_DOMAIN)


@pytest.mark.parametrize("vehicle_fixture", ["vehicle_incomplete.json"])
async def test_climate_when_operations_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
) -> None:
    """Test the climate entity is created from capabilities when operations are unknown."""
    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(SUPERB))
    assert state.state == HVACMode.HEAT_COOL


async def test_start_air_conditioning(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
) -> None:
    """Test starting the air conditioning uses the target temperature."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: ENYAQ, ATTR_HVAC_MODE: HVACMode.HEAT_COOL},
        blocking=True,
    )

    mock_skoda_client.start_air_conditioning.assert_awaited_once_with(VIN, 21.5)
    assert (state := hass.states.get(ENYAQ))
    assert state.state == HVACMode.HEAT_COOL


@pytest.mark.parametrize("vehicle_fixture", ["vehicle_incomplete.json"])
async def test_start_without_target_temperature(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
) -> None:
    """Test starting without a known target temperature keeps the vehicle's own."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: SUPERB}, blocking=True
    )

    mock_skoda_client.start_air_conditioning.assert_awaited_once_with(VIN, None)


@pytest.mark.parametrize("vehicle_fixture", ["vehicle_hybrid.json"])
async def test_stop_air_conditioning(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
) -> None:
    """Test turning the air conditioning off stops it."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: SUPERB}, blocking=True
    )

    mock_skoda_client.stop_air_conditioning.assert_awaited_once_with(VIN)
    assert (state := hass.states.get(SUPERB))
    assert state.state == HVACMode.OFF


@pytest.mark.parametrize("vehicle_fixture", ["vehicle_hybrid.json"])
async def test_set_temperature_while_running(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
) -> None:
    """Test changing the target temperature restarts the running air conditioning."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: SUPERB, ATTR_TEMPERATURE: 25},
        blocking=True,
    )

    mock_skoda_client.start_air_conditioning.assert_awaited_once_with(VIN, 25)
    assert (state := hass.states.get(SUPERB))
    assert state.attributes[ATTR_TEMPERATURE] == 25


async def test_set_temperature_while_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a target temperature set while off is kept and used on the next start."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENYAQ, ATTR_TEMPERATURE: 23},
        blocking=True,
    )
    mock_skoda_client.start_air_conditioning.assert_not_awaited()

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert (state := hass.states.get(ENYAQ))
    assert state.attributes[ATTR_TEMPERATURE] == 23

    await hass.services.async_call(
        CLIMATE_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENYAQ}, blocking=True
    )
    mock_skoda_client.start_air_conditioning.assert_awaited_once_with(VIN, 23)


async def test_vehicle_target_temperature_change(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a new target temperature reported by the vehicle replaces the shown one."""
    await setup_integration(hass, mock_config_entry)

    vehicle = mock_skoda_client.get_vehicle.return_value.vehicle
    vehicle.air_conditioning.target_temperature.value = 19.0
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENYAQ))
    assert state.attributes[ATTR_TEMPERATURE] == 19.0


@pytest.mark.parametrize(
    ("air_conditioning_state", "expected_mode", "expected_action"),
    [
        (AirConditioningState.COOLING, HVACMode.HEAT_COOL, HVACAction.COOLING),
        (AirConditioningState.HEATING, HVACMode.HEAT_COOL, HVACAction.HEATING),
        (
            AirConditioningState.HEATING_AUXILIARY,
            HVACMode.HEAT_COOL,
            HVACAction.HEATING,
        ),
        (AirConditioningState.VENTILATION, HVACMode.HEAT_COOL, HVACAction.FAN),
        (AirConditioningState.COMPLETED, HVACMode.OFF, HVACAction.OFF),
        (AirConditioningState.UNKNOWN, STATE_UNKNOWN, None),
    ],
)
async def test_climate_follows_vehicle_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    air_conditioning_state: AirConditioningState,
    expected_mode: str,
    expected_action: HVACAction | None,
) -> None:
    """Test the climate mode and action follow the air conditioning state."""
    await setup_integration(hass, mock_config_entry)

    vehicle = mock_skoda_client.get_vehicle.return_value.vehicle
    vehicle.air_conditioning.state = air_conditioning_state
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENYAQ))
    assert state.state == expected_mode
    assert state.attributes.get(ATTR_HVAC_ACTION) == expected_action


async def test_climate_action_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
) -> None:
    """Test a failed command raises a translated error and keeps the state."""
    await setup_integration(hass, mock_config_entry)
    mock_skoda_client.start_air_conditioning.side_effect = OpenApiError("boom")

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENYAQ}, blocking=True
        )

    assert exc_info.value.translation_key == "command_failed"
    assert (state := hass.states.get(ENYAQ))
    assert state.state == HVACMode.OFF
