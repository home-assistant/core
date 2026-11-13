"""Test the Tessie select platform."""

from copy import deepcopy
from typing import Any
from unittest.mock import AsyncMock, call, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from tesla_fleet_api.const import EnergyExportMode, EnergyOperationMode, Method
from tesla_fleet_api.exceptions import UnsupportedVehicle

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
    SelectService,
    SelectServiceArgument,
)
from homeassistant.components.tessie.const import (
    TessieSeatCoolerOptions,
    TessieSeatHeaterOptions,
)
from homeassistant.const import STATE_UNKNOWN, CommonServiceArgument, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .common import (
    ERROR_UNKNOWN,
    TEST_RESPONSE,
    TEST_STATE_OF_ALL_VEHICLES,
    assert_entities,
    setup_platform,
)

STEERING_WHEEL_ENTITY_ID = "select.test_steering_wheel_heat_level"
START_CLIMATE = call(
    Method.POST,
    "VINVINVIN/command/start_climate",
    params={"wait_for_completion": True, "max_attempts": 3},
)


async def test_select(
    hass: HomeAssistant, snapshot: SnapshotAssertion, entity_registry: er.EntityRegistry
) -> None:
    """Tests that the select entities are correct."""

    entry = await setup_platform(hass, [Platform.SELECT])

    assert_entities(hass, entry.entry_id, entity_registry, snapshot)

    # Test changing select
    entity_id = "select.test_seat_heater_left"
    with patch(
        "homeassistant.components.tessie.select.set_seat_heat",
        return_value=TEST_RESPONSE,
    ) as mock_set:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SelectService.SELECT_OPTION,
            {
                CommonServiceArgument.ENTITY_ID: [entity_id],
                SelectServiceArgument.OPTION: TessieSeatHeaterOptions.LOW,
            },
            blocking=True,
        )
        mock_set.assert_called_once()
    assert mock_set.call_args[1]["seat"] == "front_left"
    assert mock_set.call_args[1]["level"] == 1
    assert hass.states.get(entity_id) == snapshot(name=SERVICE_SELECT_OPTION)

    # Test site operation mode
    entity_id = "select.energy_site_operation_mode"
    with patch(
        "tesla_fleet_api.tessie.EnergySite.operation",
        return_value=TEST_RESPONSE,
    ) as call:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SelectService.SELECT_OPTION,
            {
                CommonServiceArgument.ENTITY_ID: entity_id,
                SelectServiceArgument.OPTION: EnergyOperationMode.AUTONOMOUS.value,
            },
            blocking=True,
        )
        assert (state := hass.states.get(entity_id))
        assert state.state == EnergyOperationMode.AUTONOMOUS.value
        call.assert_called_once()

    # Test site export mode
    entity_id = "select.energy_site_allow_export"
    with patch(
        "tesla_fleet_api.tessie.EnergySite.grid_import_export",
        return_value=TEST_RESPONSE,
    ) as call:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SelectService.SELECT_OPTION,
            {
                CommonServiceArgument.ENTITY_ID: entity_id,
                SelectServiceArgument.OPTION: EnergyExportMode.BATTERY_OK.value,
            },
            blocking=True,
        )
        assert (state := hass.states.get(entity_id))
        assert state.state == EnergyExportMode.BATTERY_OK.value
        call.assert_called_once()

    # Test changing select
    entity_id = "select.test_seat_cooler_left"
    with patch(
        "homeassistant.components.tessie.select.set_seat_cool",
        return_value=TEST_RESPONSE,
    ) as mock_set:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SelectService.SELECT_OPTION,
            {
                CommonServiceArgument.ENTITY_ID: [entity_id],
                SelectServiceArgument.OPTION: TessieSeatCoolerOptions.LOW,
            },
            blocking=True,
        )
        mock_set.assert_called_once()
    assert mock_set.call_args[1]["seat"] == "front_left"
    assert mock_set.call_args[1]["level"] == 1


async def test_errors(hass: HomeAssistant) -> None:
    """Tests unknown error is handled."""

    await setup_platform(hass, [Platform.SELECT])

    # Test changing vehicle select with unknown error
    with (
        patch(
            "homeassistant.components.tessie.select.set_seat_heat",
            side_effect=ERROR_UNKNOWN,
        ) as mock_set,
        pytest.raises(HomeAssistantError) as error,
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SelectService.SELECT_OPTION,
            {
                CommonServiceArgument.ENTITY_ID: ["select.test_seat_heater_left"],
                SelectServiceArgument.OPTION: TessieSeatHeaterOptions.LOW,
            },
            blocking=True,
        )
    mock_set.assert_called_once()
    assert error.value.__cause__ == ERROR_UNKNOWN
    assert error.value.translation_domain == "tessie"
    assert error.value.translation_key == "cannot_connect"

    # Test changing energy select with unknown error
    with (
        patch(
            "tesla_fleet_api.tessie.EnergySite.operation",
            side_effect=UnsupportedVehicle,
        ) as mock_set,
        pytest.raises(HomeAssistantError) as error,
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SelectService.SELECT_OPTION,
            {
                CommonServiceArgument.ENTITY_ID: ["select.energy_site_operation_mode"],
                SelectServiceArgument.OPTION: EnergyOperationMode.AUTONOMOUS.value,
            },
            blocking=True,
        )
    mock_set.assert_called_once()
    assert isinstance(error.value.__cause__, UnsupportedVehicle)


def _steering_wheel_level(level: int) -> Any:
    return call(
        Method.POST,
        "api/1/vehicles/VINVINVIN/command/remote_steering_wheel_heat_level_request",
        json={"level": level},
    )


@pytest.mark.parametrize(
    ("option", "climate_on", "expected_calls"),
    [
        pytest.param(
            TessieSeatHeaterOptions.OFF, False, [_steering_wheel_level(0)], id="off"
        ),
        pytest.param(
            TessieSeatHeaterOptions.HIGH,
            False,
            [START_CLIMATE, _steering_wheel_level(3)],
            id="high_starts_climate",
        ),
        pytest.param(
            TessieSeatHeaterOptions.LOW,
            True,
            [_steering_wheel_level(1)],
            id="low_with_climate_on",
        ),
    ],
)
async def test_steering_wheel_heater(
    hass: HomeAssistant,
    mock_get_state_of_all_vehicles: AsyncMock,
    mock_request: AsyncMock,
    option: TessieSeatHeaterOptions,
    climate_on: bool,
    expected_calls: list[Any],
) -> None:
    """Test setting the steering wheel heat level through the Fleet API proxy."""
    vehicles = deepcopy(TEST_STATE_OF_ALL_VEHICLES)
    vehicles["results"][0]["last_state"]["climate_state"]["is_climate_on"] = climate_on
    mock_get_state_of_all_vehicles.return_value = vehicles
    await setup_platform(hass, [Platform.SELECT])
    mock_request.reset_mock()

    await hass.services.async_call(
        SELECT_DOMAIN,
        SelectService.SELECT_OPTION,
        {
            CommonServiceArgument.ENTITY_ID: STEERING_WHEEL_ENTITY_ID,
            SelectServiceArgument.OPTION: option,
        },
        blocking=True,
    )

    assert mock_request.call_args_list == expected_calls
    assert (entity_state := hass.states.get(STEERING_WHEEL_ENTITY_ID))
    assert entity_state.state == option


@pytest.mark.parametrize(
    ("level", "expected"),
    [
        pytest.param(1, TessieSeatHeaterOptions.LOW, id="low"),
        pytest.param(3, TessieSeatHeaterOptions.HIGH, id="high"),
        pytest.param(4, TessieSeatHeaterOptions.HIGH, id="above_high"),
        pytest.param("SNA", STATE_UNKNOWN, id="signal_not_available"),
    ],
)
async def test_steering_wheel_heater_state(
    hass: HomeAssistant,
    mock_get_state_of_all_vehicles: AsyncMock,
    level: int | str,
    expected: str,
) -> None:
    """Test the steering wheel heat levels the vehicle reports."""
    vehicles = deepcopy(TEST_STATE_OF_ALL_VEHICLES)
    vehicles["results"][0]["last_state"]["climate_state"][
        "steering_wheel_heat_level"
    ] = level
    mock_get_state_of_all_vehicles.return_value = vehicles
    await setup_platform(hass, [Platform.SELECT])

    assert (entity_state := hass.states.get(STEERING_WHEEL_ENTITY_ID))
    assert entity_state.state == expected


@pytest.mark.parametrize(
    ("response", "translation_key"),
    [
        pytest.param(
            {"response": {"result": False, "reason": "could_not_wake_buses"}},
            "command_failed",
            id="reason",
        ),
        pytest.param(
            {"response": {"result": False, "reason": ""}},
            "unknown",
            id="no_reason",
        ),
        pytest.param(
            {"response": None, "error": "vehicle unavailable"},
            "command_failed",
            id="error",
        ),
        pytest.param({"response": None}, "unknown", id="no_response"),
    ],
)
async def test_steering_wheel_heater_rejected(
    hass: HomeAssistant,
    mock_get_state_of_all_vehicles: AsyncMock,
    mock_request: AsyncMock,
    response: dict[str, Any],
    translation_key: str,
) -> None:
    """Test a steering wheel heat level the vehicle rejects is not kept."""
    vehicles = deepcopy(TEST_STATE_OF_ALL_VEHICLES)
    vehicles["results"][0]["last_state"]["climate_state"]["is_climate_on"] = True
    mock_get_state_of_all_vehicles.return_value = vehicles
    await setup_platform(hass, [Platform.SELECT])
    mock_request.return_value = response

    with pytest.raises(HomeAssistantError) as error:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SelectService.SELECT_OPTION,
            {
                CommonServiceArgument.ENTITY_ID: STEERING_WHEEL_ENTITY_ID,
                SelectServiceArgument.OPTION: TessieSeatHeaterOptions.LOW,
            },
            blocking=True,
        )

    assert error.value.translation_domain == "tessie"
    assert error.value.translation_key == translation_key
    assert (entity_state := hass.states.get(STEERING_WHEEL_ENTITY_ID))
    assert entity_state.state == TessieSeatHeaterOptions.OFF


async def test_steering_wheel_heater_already_set(
    hass: HomeAssistant,
    mock_get_state_of_all_vehicles: AsyncMock,
    mock_request: AsyncMock,
) -> None:
    """Test an already set steering wheel heat level is accepted."""
    vehicles = deepcopy(TEST_STATE_OF_ALL_VEHICLES)
    vehicles["results"][0]["last_state"]["climate_state"]["is_climate_on"] = True
    mock_get_state_of_all_vehicles.return_value = vehicles
    await setup_platform(hass, [Platform.SELECT])
    mock_request.return_value = {"response": {"result": False, "reason": "already_set"}}

    await hass.services.async_call(
        SELECT_DOMAIN,
        SelectService.SELECT_OPTION,
        {
            CommonServiceArgument.ENTITY_ID: STEERING_WHEEL_ENTITY_ID,
            SelectServiceArgument.OPTION: TessieSeatHeaterOptions.LOW,
        },
        blocking=True,
    )

    assert (entity_state := hass.states.get(STEERING_WHEEL_ENTITY_ID))
    assert entity_state.state == TessieSeatHeaterOptions.LOW
