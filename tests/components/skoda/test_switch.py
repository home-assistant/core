"""Test the Škoda switch platform."""

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
from skoda_public_api.api_layer.exceptions import (
    OpenApiError,
    OpenApiRateLimitError,
    OpenApiServerError,
    OpenApiTimeoutError,
    OpenApiUnsupportedError,
)
from skoda_public_api.models.enums import ChargingState, VentilationState
from skoda_public_api.models.vehicle import VehicleResponse
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.skoda.const import DOMAIN
from homeassistant.components.skoda.coordinator import UPDATE_INTERVAL
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import VIN


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Only set up the switch platform."""
    with patch("homeassistant.components.skoda._PLATFORMS", [Platform.SWITCH]):
        yield


@pytest.mark.usefixtures("mock_skoda_client")
@pytest.mark.parametrize(
    "vehicle_fixture",
    ["vehicle_electric.json", "vehicle_hybrid.json", "vehicle_combustion.json"],
)
async def test_switches(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Škoda switch entities against a snapshot."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_no_switch_without_operation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test no switch is created when the vehicle does not support the operation."""
    vehicle = await async_load_json_object_fixture(
        hass, "vehicle_electric.json", DOMAIN
    )
    vehicle["vehicle"]["operations"] = [{"name": "startAirConditioning"}]
    mock_skoda_client.get_vehicle.return_value = VehicleResponse.model_validate(vehicle)

    await setup_integration(hass, mock_config_entry)

    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )


@pytest.mark.parametrize("vehicle_fixture", ["vehicle_incomplete.json"])
async def test_switch_when_operations_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
) -> None:
    """Test the switch is created from capabilities when operations are unknown."""
    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get("switch.superb_charging"))
    assert state.state == STATE_ON


@pytest.mark.parametrize(
    ("vehicle_fixture", "entity_id", "service", "method", "expected_state"),
    [
        (
            "vehicle_electric.json",
            "switch.enyaq_coupe_charging",
            SERVICE_TURN_OFF,
            "stop_charging",
            STATE_OFF,
        ),
        (
            "vehicle_hybrid.json",
            "switch.superb_charging",
            SERVICE_TURN_ON,
            "start_charging",
            STATE_ON,
        ),
        (
            "vehicle_combustion.json",
            "switch.octavia_active_ventilation",
            SERVICE_TURN_ON,
            "start_active_ventilation",
            STATE_ON,
        ),
        (
            "vehicle_combustion.json",
            "switch.octavia_active_ventilation",
            SERVICE_TURN_OFF,
            "stop_active_ventilation",
            STATE_OFF,
        ),
    ],
)
async def test_switch_actions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
    entity_id: str,
    service: str,
    method: str,
    expected_state: str,
) -> None:
    """Test switch actions send the command and update the state."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SWITCH_DOMAIN, service, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )

    getattr(mock_skoda_client, method).assert_awaited_once_with(VIN)
    assert (state := hass.states.get(entity_id))
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("error", "translation_key"),
    [
        (OpenApiError("boom"), "command_failed"),
        (OpenApiUnsupportedError(), "command_not_supported"),
        (OpenApiRateLimitError(), "rate_limit_exceeded"),
        (OpenApiServerError("timeout", 504), "vehicle_not_responding"),
        (OpenApiTimeoutError(), "vehicle_not_responding"),
    ],
)
async def test_switch_action_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
    error: OpenApiError,
    translation_key: str,
) -> None:
    """Test a failed command raises a translated error and keeps the state."""
    await setup_integration(hass, mock_config_entry)
    mock_skoda_client.stop_charging.side_effect = error

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.enyaq_coupe_charging"},
            blocking=True,
        )

    assert exc_info.value.translation_key == translation_key
    assert (state := hass.states.get("switch.enyaq_coupe_charging"))
    assert state.state == STATE_ON


@pytest.mark.parametrize(
    ("charging_state", "expected_state"),
    [
        (ChargingState.CHARGING, STATE_ON),
        (ChargingState.UNKNOWN, STATE_UNKNOWN),
    ],
)
@pytest.mark.parametrize("vehicle_fixture", ["vehicle_hybrid.json"])
async def test_switch_updates_from_vehicle(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    charging_state: ChargingState,
    expected_state: str,
) -> None:
    """Test the switch follows the charging state reported by the vehicle."""
    await setup_integration(hass, mock_config_entry)
    assert (state := hass.states.get("switch.superb_charging"))
    assert state.state == STATE_OFF

    vehicle = mock_skoda_client.get_vehicle.return_value.vehicle
    vehicle.charging.status.state = charging_state
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get("switch.superb_charging"))
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("ventilation_state", "expected_state"),
    [
        (VentilationState.PREHEATING, STATE_ON),
        (VentilationState.VENTILATION, STATE_ON),
        (VentilationState.UNKNOWN, STATE_UNKNOWN),
    ],
)
@pytest.mark.parametrize("vehicle_fixture", ["vehicle_combustion.json"])
async def test_active_ventilation_updates_from_vehicle(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    ventilation_state: VentilationState,
    expected_state: str,
) -> None:
    """Test the switch follows the ventilation state reported by the vehicle."""
    await setup_integration(hass, mock_config_entry)
    assert (state := hass.states.get("switch.octavia_active_ventilation"))
    assert state.state == STATE_OFF

    vehicle = mock_skoda_client.get_vehicle.return_value.vehicle
    vehicle.active_ventilation.state = ventilation_state
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get("switch.octavia_active_ventilation"))
    assert state.state == expected_state


@pytest.mark.parametrize(
    ("vehicle_fixture", "entity_id"),
    [
        ("vehicle_electric.json", "switch.enyaq_coupe_charging"),
        ("vehicle_combustion.json", "switch.octavia_active_ventilation"),
    ],
)
async def test_switch_unknown_when_data_missing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    entity_id: str,
) -> None:
    """Test the switch reports unknown when a later update lacks its data."""
    await setup_integration(hass, mock_config_entry)

    mock_skoda_client.get_vehicle.return_value = VehicleResponse.model_validate(
        await async_load_json_object_fixture(hass, "vehicle_unavailable.json", DOMAIN)
    )
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNKNOWN
