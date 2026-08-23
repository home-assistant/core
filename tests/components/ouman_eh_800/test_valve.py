"""Tests for the Ouman EH-800 valve platform."""

from unittest.mock import AsyncMock

from ouman_eh_800_api import (
    L1BaseEndpoints,
    OumanClientAuthenticationError,
    OumanClientCommunicationError,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.valve import (
    ATTR_POSITION,
    DOMAIN as VALVE_DOMAIN,
    SERVICE_CLOSE_VALVE,
    SERVICE_OPEN_VALVE,
    SERVICE_SET_VALVE_POSITION,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


# Only L1 and L2 base endpoints produce valve entities. A single scenario
# that exposes both is enough to cover the snapshot; the relay-only and
# single-circuit scenarios would either be empty or duplicate this output.
@pytest.mark.parametrize("scenario", ["room_sensors"], indirect=True)
@pytest.mark.parametrize("init_integration", [Platform.VALVE], indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the valve entities for each registry-set scenario."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("init_integration", [Platform.VALVE], indirect=True)
@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("service", "service_data", "expected_position"),
    [
        pytest.param(
            SERVICE_SET_VALVE_POSITION,
            {ATTR_POSITION: 42},
            42,
            id="set_position",
        ),
        pytest.param(SERVICE_OPEN_VALVE, {}, 100, id="open"),
        pytest.param(SERVICE_CLOSE_VALVE, {}, 0, id="close"),
    ],
)
async def test_async_set_valve_position(
    hass: HomeAssistant,
    mock_ouman_client: AsyncMock,
    service: str,
    service_data: dict[str, int],
    expected_position: int,
) -> None:
    """Test that valve services write to the device and update state."""
    entity_id = "valve.heating_circuit_1_patterilammitys_valve_position_setpoint"

    await hass.services.async_call(
        VALVE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id, **service_data},
        blocking=True,
    )

    mock_ouman_client.set_endpoint_value.assert_called_once_with(
        L1BaseEndpoints.VALVE_POSITION_SETPOINT, expected_position
    )
    assert (
        hass.states.get(entity_id).attributes["current_position"] == expected_position
    )


@pytest.mark.parametrize("init_integration", [Platform.VALVE], indirect=True)
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
async def test_async_set_valve_position_errors(
    hass: HomeAssistant,
    mock_ouman_client: AsyncMock,
    client_error: Exception,
    expected_message: str,
) -> None:
    """Test that client errors are mapped to HomeAssistantError."""
    mock_ouman_client.set_endpoint_value.side_effect = client_error

    with pytest.raises(HomeAssistantError, match=expected_message):
        await hass.services.async_call(
            VALVE_DOMAIN,
            SERVICE_SET_VALVE_POSITION,
            {
                ATTR_ENTITY_ID: "valve.heating_circuit_1_patterilammitys_valve_position_setpoint",
                ATTR_POSITION: 50,
            },
            blocking=True,
        )

    mock_ouman_client.set_endpoint_value.assert_called_once_with(
        L1BaseEndpoints.VALVE_POSITION_SETPOINT, 50
    )
