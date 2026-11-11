"""Test the Škoda number platform."""

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
from skoda_public_api.models.vehicle import VehicleResponse
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.components.skoda.const import DOMAIN
from homeassistant.components.skoda.coordinator import UPDATE_INTERVAL
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import VIN

CHARGE_LIMIT_ENTITY_ID = "number.enyaq_coupe_charge_limit"


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Only set up the number platform."""
    with patch("homeassistant.components.skoda._PLATFORMS", [Platform.NUMBER]):
        yield


@pytest.mark.usefixtures("mock_skoda_client")
@pytest.mark.parametrize(
    "vehicle_fixture", ["vehicle_electric.json", "vehicle_hybrid.json"]
)
async def test_numbers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Škoda number entities against a snapshot."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("vehicle_fixture", "operations"),
    [
        pytest.param(
            "vehicle_combustion.json",
            [{"name": "setChargingLimit"}],
            id="no_charging_capability",
        ),
        pytest.param(
            "vehicle_electric.json",
            [{"name": "startCharging"}],
            id="no_charging_limit_operation",
        ),
    ],
)
async def test_no_number_when_unsupported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    vehicle_fixture: str,
    operations: list[dict[str, str]],
) -> None:
    """Test no number entity is created when the vehicle does not support it."""
    vehicle = await async_load_json_object_fixture(hass, vehicle_fixture, DOMAIN)
    vehicle["vehicle"]["operations"] = operations
    mock_skoda_client.get_vehicle.return_value = VehicleResponse.model_validate(vehicle)

    await setup_integration(hass, mock_config_entry)

    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )


@pytest.mark.parametrize("vehicle_fixture", ["vehicle_incomplete.json"])
async def test_number_when_operations_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
) -> None:
    """Test the number entity is created from capabilities when operations are unknown."""
    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get("number.superb_charge_limit"))
    assert state.state == STATE_UNKNOWN


async def test_set_charge_limit(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
) -> None:
    """Test setting the charge limit sends the command and updates the state."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: CHARGE_LIMIT_ENTITY_ID, ATTR_VALUE: 60},
        blocking=True,
    )

    mock_skoda_client.set_charge_limit.assert_awaited_once_with(VIN, 60)
    assert (state := hass.states.get(CHARGE_LIMIT_ENTITY_ID))
    assert state.state == "60"


async def test_set_charge_limit_off_step(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
) -> None:
    """Test a charge limit between steps is rejected without calling the API."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: CHARGE_LIMIT_ENTITY_ID, ATTR_VALUE: 55},
            blocking=True,
        )

    assert exc_info.value.translation_key == "invalid_step"
    mock_skoda_client.set_charge_limit.assert_not_awaited()


async def test_set_charge_limit_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
) -> None:
    """Test a failed command raises a translated error and keeps the value."""
    await setup_integration(hass, mock_config_entry)
    mock_skoda_client.set_charge_limit.side_effect = OpenApiError("boom")

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: CHARGE_LIMIT_ENTITY_ID, ATTR_VALUE: 60},
            blocking=True,
        )

    assert exc_info.value.translation_key == "command_failed"
    assert (state := hass.states.get(CHARGE_LIMIT_ENTITY_ID))
    assert state.state == "80"


async def test_number_updates_from_vehicle(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the charge limit follows the value reported by the vehicle."""
    await setup_integration(hass, mock_config_entry)

    vehicle = mock_skoda_client.get_vehicle.return_value.vehicle
    vehicle.charging.settings.target_state_of_charge_in_percent = 90
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(CHARGE_LIMIT_ENTITY_ID))
    assert state.state == "90"


async def test_number_unknown_when_data_missing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_skoda_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the charge limit reports unknown when a later update lacks its data."""
    await setup_integration(hass, mock_config_entry)

    mock_skoda_client.get_vehicle.return_value = VehicleResponse.model_validate(
        await async_load_json_object_fixture(hass, "vehicle_unavailable.json", DOMAIN)
    )
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(CHARGE_LIMIT_ENTITY_ID))
    assert state.state == STATE_UNKNOWN
