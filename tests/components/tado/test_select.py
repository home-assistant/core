"""The select tests for the tado platform."""

from unittest.mock import patch

import pytest

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_OPTION
from homeassistant.core import HomeAssistant

from .util import async_init_integration

HEATING_CIRCUIT_SELECT_ENTITY = "select.baseboard_heater_heating_circuit"
NO_HEATING_CIRCUIT = "no_heating_circuit"
HEATING_CIRCUIT_OPTION = "RU1234567890"


async def test_heating_circuit_select(hass: HomeAssistant) -> None:
    """Test creation of heating circuit select entity."""

    await async_init_integration(hass)
    state = hass.states.get(HEATING_CIRCUIT_SELECT_ENTITY)
    assert state is not None
    assert state.state == HEATING_CIRCUIT_OPTION
    assert NO_HEATING_CIRCUIT in state.attributes["options"]
    assert HEATING_CIRCUIT_OPTION in state.attributes["options"]


async def test_select_heating_circuit(hass: HomeAssistant) -> None:
    """Test selecting heating circuit option."""

    await async_init_integration(hass)

    # Test selecting a specific heating circuit
    with (
        patch(
            "homeassistant.components.tado.TadoDataUpdateCoordinator.set_heating_circuit"
        ) as mock_set_heating_circuit,
        patch(
            "homeassistant.components.tado.TadoDataUpdateCoordinator.async_request_refresh"
        ) as mock_refresh,
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: HEATING_CIRCUIT_SELECT_ENTITY,
                ATTR_OPTION: HEATING_CIRCUIT_OPTION,
            },
            blocking=True,
        )

    mock_set_heating_circuit.assert_called_once()
    # The heating circuit ID should be extracted from the coordinator data
    assert mock_refresh.called


async def test_select_no_heating_circuit(hass: HomeAssistant) -> None:
    """Test selecting no heating circuit option."""

    await async_init_integration(hass)

    # Test selecting no heating circuit
    with (
        patch(
            "homeassistant.components.tado.TadoDataUpdateCoordinator.set_heating_circuit"
        ) as mock_set_heating_circuit,
        patch(
            "homeassistant.components.tado.TadoDataUpdateCoordinator.async_request_refresh"
        ) as mock_refresh,
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: HEATING_CIRCUIT_SELECT_ENTITY,
                ATTR_OPTION: NO_HEATING_CIRCUIT,
            },
            blocking=True,
        )

    mock_set_heating_circuit.assert_called_once()
    # None should be passed when selecting "no_heating_circuit"
    assert mock_set_heating_circuit.call_args[0][1] is None
    assert mock_refresh.called


async def test_coordinator_update(hass: HomeAssistant) -> None:
    """Test coordinator update handling."""

    await async_init_integration(hass)

    entity = hass.data["entity_components"]["select"].get_entity(
        HEATING_CIRCUIT_SELECT_ENTITY
    )
    assert entity is not None

    # Simulate coordinator update with new heating circuit data
    with patch.object(entity, "_async_update_callback") as mock_update_callback:
        await entity.coordinator.async_refresh()

    assert mock_update_callback.called


@pytest.mark.usefixtures("caplog")
async def test_heating_circuit_not_found(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test when a heating circuit with a specific number is not found."""

    await async_init_integration(hass)
    entity = hass.data["entity_components"]["select"].get_entity(
        HEATING_CIRCUIT_SELECT_ENTITY
    )

    # Prepare test data with a heating circuit number that doesn't exist
    nonexistent_circuit_number = 999

    # Create a modified zone_control
    modified_zone_control = {
        "heatingCircuit": nonexistent_circuit_number,
        "type": "HEATING",
    }

    # Replace the zone_control data in the coordinator
    with patch.dict(
        entity.coordinator.data["zone_control"], {entity.zone_id: modified_zone_control}
    ):
        # Force an update callback
        entity._async_update_callback()

    # Check that error was logged
    assert any(
        f"Heating circuit with number {nonexistent_circuit_number} not found for zone"
        in record.message
        for record in caplog.records
    )
    # Check that the entity falls back to no heating circuit
    assert entity.current_option == NO_HEATING_CIRCUIT


@pytest.mark.usefixtures("caplog")
async def test_keyerror_handling(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test handling of KeyError in _async_update_callback."""

    await async_init_integration(hass)
    entity = hass.data["entity_components"]["select"].get_entity(
        HEATING_CIRCUIT_SELECT_ENTITY
    )

    # Create a coordinator with incomplete data that will trigger a KeyError
    with patch.object(
        entity.coordinator,
        "data",
        # Missing 'heating_circuits' key will trigger KeyError
        {"zone_control": {}},
    ):
        # Force an update callback
        entity._async_update_callback()

    # Check that error was logged
    assert any(
        f"Could not update heating circuit info for zone {entity.zone_name}"
        in record.message
        for record in caplog.records
    )
