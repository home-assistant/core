"""Test the Tessie select platform."""

from unittest.mock import patch

import pytest
from syrupy import SnapshotAssertion
from tesla_fleet_api.const import EnergyExportMode, EnergyOperationMode
from tesla_fleet_api.exceptions import UnsupportedVehicle

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.tessie.const import (
    TessieSeatCoolerOptions,
    TessieSeatHeaterOptions,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_OPTION, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .common import TEST_RESPONSE, assert_entities, error_unknown, setup_platform


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
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: [entity_id], ATTR_OPTION: TessieSeatHeaterOptions.LOW},
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
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: entity_id,
                ATTR_OPTION: EnergyOperationMode.AUTONOMOUS.value,
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
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: EnergyExportMode.BATTERY_OK.value},
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
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: [entity_id], ATTR_OPTION: TessieSeatCoolerOptions.LOW},
            blocking=True,
        )
        mock_set.assert_called_once()
    assert mock_set.call_args[1]["seat"] == "front_left"
    assert mock_set.call_args[1]["level"] == 1


async def test_errors(hass: HomeAssistant) -> None:
    """Tests unknown error is handled."""

    await setup_platform(hass, [Platform.SELECT])

    # Test changing vehicle select with unknown error
    exc = error_unknown()
    with (
        patch(
            "homeassistant.components.tessie.select.set_seat_heat",
            side_effect=exc,
        ) as mock_set,
        pytest.raises(HomeAssistantError) as error,
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: ["select.test_seat_heater_left"],
                ATTR_OPTION: TessieSeatHeaterOptions.LOW,
            },
            blocking=True,
        )
    mock_set.assert_called_once()
    assert error.value.__cause__ == exc

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
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: ["select.energy_site_operation_mode"],
                ATTR_OPTION: EnergyOperationMode.AUTONOMOUS.value,
            },
            blocking=True,
        )
    mock_set.assert_called_once()
    assert isinstance(error.value.__cause__, UnsupportedVehicle)
