"""Tests for the Ouman EH-800 number platform."""

from unittest.mock import AsyncMock

from ouman_eh_800_api import (
    FloatControlOumanEndpoint,
    IntControlOumanEndpoint,
    L1BaseEndpoints,
    L1RoomSensor,
    L1ThreePointCurve,
    OumanClientAuthenticationError,
    OumanClientCommunicationError,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import SCENARIOS

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize("scenario", SCENARIOS.keys(), indirect=True)
@pytest.mark.parametrize("init_integration", [Platform.NUMBER], indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the number entities for each registry-set scenario."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("init_integration", [Platform.NUMBER], indirect=True)
@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("entity_id", "endpoint", "initial_value", "target_value", "set_value"),
    [
        pytest.param(
            "number.heating_circuit_1_patterilammitys_curve_0degc_temperature",
            L1ThreePointCurve.CURVE_0_TEMP,
            41.0,
            42.0,
            42.0,
            id="int_setpoint",
        ),
        pytest.param(
            "number.heating_circuit_1_patterilammitys_room_temperature_fine_tuning",
            L1RoomSensor.ROOM_TEMPERATURE_FINE_TUNING,
            0.0,
            1.5,
            1.5,
            id="float_fine_tuning",
        ),
    ],
)
async def test_async_set_native_value(
    hass: HomeAssistant,
    mock_ouman_client: AsyncMock,
    entity_id: str,
    endpoint: IntControlOumanEndpoint | FloatControlOumanEndpoint,
    initial_value: float,
    target_value: float,
    set_value: float,
) -> None:
    """Test that setting a number writes to the device and updates state."""
    assert float(hass.states.get(entity_id).state) == initial_value

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: target_value},
        blocking=True,
    )

    mock_ouman_client.set_endpoint_value.assert_called_once_with(endpoint, set_value)
    assert float(hass.states.get(entity_id).state) == target_value


@pytest.mark.parametrize("init_integration", [Platform.NUMBER], indirect=True)
@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("client_error", "expected_message"),
    [
        pytest.param(
            OumanClientAuthenticationError("Wrong username or password"),
            "Authentication failed",
            id="auth_failure",
        ),
        pytest.param(
            OumanClientCommunicationError("Network error: Connection refused"),
            "Error communicating with API",
            id="communication_failure",
        ),
    ],
)
async def test_async_set_native_value_errors(
    hass: HomeAssistant,
    mock_ouman_client: AsyncMock,
    client_error: Exception,
    expected_message: str,
) -> None:
    """Test that client errors are mapped to HomeAssistantError."""
    mock_ouman_client.set_endpoint_value.side_effect = client_error

    with pytest.raises(HomeAssistantError, match=expected_message):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "number.heating_circuit_1_patterilammitys_water_out_minimum_temperature",
                ATTR_VALUE: 20,
            },
            blocking=True,
        )

    # First positional arg is the endpoint; we only assert the call happened.
    mock_ouman_client.set_endpoint_value.assert_called_once()
    args, _ = mock_ouman_client.set_endpoint_value.call_args
    assert args[0] is L1BaseEndpoints.WATER_OUT_MIN_TEMP
    assert args[1] == 20
