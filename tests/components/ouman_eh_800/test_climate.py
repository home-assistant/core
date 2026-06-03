"""Tests for the Ouman EH-800 climate platform."""

from unittest.mock import AsyncMock, call

from ouman_eh_800_api import (
    L1BaseEndpoints,
    L1RoomSensor,
    OperationMode,
    OumanClientAuthenticationError,
    OumanClientCommunicationError,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


# Climate entities only exist on circuits with a room sensor; the
# ``room_sensors`` scenario activates both L1RoomSensor and L2RoomSensor.
@pytest.mark.parametrize("scenario", ["room_sensors"], indirect=True)
@pytest.mark.parametrize("init_integration", [Platform.CLIMATE], indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the climate entities for the room-sensor scenario."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("scenario", ["no_room_sensors"], indirect=True)
@pytest.mark.parametrize("init_integration", [Platform.CLIMATE], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_no_climate_when_no_room_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Verify no climate entities are created when no circuit has a room sensor."""
    assert (
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
        == []
    )


@pytest.mark.parametrize("init_integration", [Platform.CLIMATE], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_async_set_temperature(
    hass: HomeAssistant, mock_ouman_client: AsyncMock
) -> None:
    """Test that setting the target temperature writes to the device and updates state."""
    entity_id = "climate.heating_circuit_1_patterilammitys"

    assert hass.states.get(entity_id).attributes["temperature"] == 21.0

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ATTR_TEMPERATURE: 22.0},
        blocking=True,
    )

    mock_ouman_client.set_endpoint_value.assert_called_once_with(
        L1RoomSensor.ROOM_TEMPERATURE_SETPOINT_USER, 22
    )
    assert hass.states.get(entity_id).attributes["temperature"] == 22.0


@pytest.mark.parametrize("init_integration", [Platform.CLIMATE], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_async_set_temperature_with_hvac_mode(
    hass: HomeAssistant, mock_ouman_client: AsyncMock
) -> None:
    """Test that set_temperature with hvac_mode writes both mode and setpoint."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: "climate.heating_circuit_1_patterilammitys",
            ATTR_TEMPERATURE: 22.0,
            ATTR_HVAC_MODE: HVACMode.OFF,
        },
        blocking=True,
    )

    assert mock_ouman_client.set_endpoint_value.call_args_list == [
        call(L1BaseEndpoints.OPERATION_MODE, OperationMode.SHUTDOWN),
        call(L1RoomSensor.ROOM_TEMPERATURE_SETPOINT_USER, 22),
    ]


@pytest.mark.parametrize("init_integration", [Platform.CLIMATE], indirect=True)
@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("operation_mode", "expected_hvac_mode"),
    [
        pytest.param(OperationMode.AUTOMATIC, HVACMode.HEAT, id="automatic"),
        pytest.param(OperationMode.TEMPERATURE_DROP, HVACMode.HEAT, id="temp_drop"),
        pytest.param(
            OperationMode.BIG_TEMPERATURE_DROP, HVACMode.HEAT, id="big_temp_drop"
        ),
        pytest.param(OperationMode.NORMAL_TEMPERATURE, HVACMode.OFF, id="normal"),
        pytest.param(
            OperationMode.MANUAL_VALVE_CONTROL, HVACMode.OFF, id="manual_valve"
        ),
        pytest.param(OperationMode.SHUTDOWN, HVACMode.OFF, id="shutdown"),
    ],
)
async def test_hvac_mode_mapping(
    hass: HomeAssistant,
    mock_ouman_client: AsyncMock,
    operation_mode: OperationMode,
    expected_hvac_mode: HVACMode,
) -> None:
    """Test that the operation mode maps to the expected HVAC mode."""
    mock_ouman_client.get_values.return_value[L1BaseEndpoints.OPERATION_MODE] = (
        operation_mode
    )
    await hass.config_entries.async_reload(
        hass.config_entries.async_entries("ouman_eh_800")[0].entry_id
    )
    await hass.async_block_till_done()

    state = hass.states.get("climate.heating_circuit_1_patterilammitys")
    assert state.state == expected_hvac_mode


@pytest.mark.parametrize("init_integration", [Platform.CLIMATE], indirect=True)
@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("operation_mode", "valve_position", "expected_hvac_action"),
    [
        pytest.param(
            OperationMode.AUTOMATIC, 11.0, HVACAction.HEATING, id="heating_when_open"
        ),
        pytest.param(
            OperationMode.AUTOMATIC, 0.0, HVACAction.IDLE, id="idle_when_closed"
        ),
        pytest.param(
            OperationMode.SHUTDOWN, 0.0, HVACAction.OFF, id="off_when_shutdown"
        ),
        pytest.param(
            OperationMode.MANUAL_VALVE_CONTROL,
            50.0,
            HVACAction.OFF,
            id="off_when_manual_valve_even_if_open",
        ),
    ],
)
async def test_hvac_action_mapping(
    hass: HomeAssistant,
    mock_ouman_client: AsyncMock,
    operation_mode: OperationMode,
    valve_position: float,
    expected_hvac_action: HVACAction,
) -> None:
    """Test that hvac_action reflects operation mode and valve position."""
    values = mock_ouman_client.get_values.return_value
    values[L1BaseEndpoints.OPERATION_MODE] = operation_mode
    values[L1BaseEndpoints.VALVE_POSITION] = valve_position
    await hass.config_entries.async_reload(
        hass.config_entries.async_entries("ouman_eh_800")[0].entry_id
    )
    await hass.async_block_till_done()

    state = hass.states.get("climate.heating_circuit_1_patterilammitys")
    assert state.attributes["hvac_action"] == expected_hvac_action


@pytest.mark.parametrize("init_integration", [Platform.CLIMATE], indirect=True)
@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("hvac_mode", "expected_operation_mode"),
    [
        pytest.param(HVACMode.HEAT, OperationMode.AUTOMATIC, id="heat"),
        pytest.param(HVACMode.OFF, OperationMode.SHUTDOWN, id="off"),
    ],
)
async def test_async_set_hvac_mode(
    hass: HomeAssistant,
    mock_ouman_client: AsyncMock,
    hvac_mode: HVACMode,
    expected_operation_mode: OperationMode,
) -> None:
    """Test that HVAC mode writes the corresponding operation mode."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {
            ATTR_ENTITY_ID: "climate.heating_circuit_1_patterilammitys",
            ATTR_HVAC_MODE: hvac_mode,
        },
        blocking=True,
    )

    mock_ouman_client.set_endpoint_value.assert_called_once_with(
        L1BaseEndpoints.OPERATION_MODE, expected_operation_mode
    )


@pytest.mark.parametrize("init_integration", [Platform.CLIMATE], indirect=True)
@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("preset_mode", "expected_operation_mode"),
    [
        pytest.param("automatic", OperationMode.AUTOMATIC, id="automatic"),
        pytest.param(
            "temperature_drop", OperationMode.TEMPERATURE_DROP, id="temp_drop"
        ),
        pytest.param(
            "big_temperature_drop",
            OperationMode.BIG_TEMPERATURE_DROP,
            id="big_temp_drop",
        ),
    ],
)
async def test_async_set_preset_mode(
    hass: HomeAssistant,
    mock_ouman_client: AsyncMock,
    preset_mode: str,
    expected_operation_mode: OperationMode,
) -> None:
    """Test that the preset_mode writes the corresponding operation mode."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {
            ATTR_ENTITY_ID: "climate.heating_circuit_1_patterilammitys",
            ATTR_PRESET_MODE: preset_mode,
        },
        blocking=True,
    )

    mock_ouman_client.set_endpoint_value.assert_called_once_with(
        L1BaseEndpoints.OPERATION_MODE, expected_operation_mode
    )


@pytest.mark.parametrize("init_integration", [Platform.CLIMATE], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_async_set_preset_mode_invalid(
    hass: HomeAssistant, mock_ouman_client: AsyncMock
) -> None:
    """Test that an unknown preset is rejected by the service validation."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {
                ATTR_ENTITY_ID: "climate.heating_circuit_1_patterilammitys",
                ATTR_PRESET_MODE: "nonexistent",
            },
            blocking=True,
        )

    mock_ouman_client.set_endpoint_value.assert_not_called()


@pytest.mark.parametrize("init_integration", [Platform.CLIMATE], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_async_set_temperature_out_of_range(
    hass: HomeAssistant, mock_ouman_client: AsyncMock
) -> None:
    """Test that setting a target temperature outside the device range is rejected."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: "climate.heating_circuit_1_patterilammitys",
                ATTR_TEMPERATURE: 99.0,
            },
            blocking=True,
        )

    mock_ouman_client.set_endpoint_value.assert_not_called()


@pytest.mark.parametrize("init_integration", [Platform.CLIMATE], indirect=True)
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
async def test_async_set_temperature_errors(
    hass: HomeAssistant,
    mock_ouman_client: AsyncMock,
    client_error: Exception,
    expected_message: str,
) -> None:
    """Test that client errors are mapped to HomeAssistantError."""
    mock_ouman_client.set_endpoint_value.side_effect = client_error

    with pytest.raises(HomeAssistantError, match=expected_message):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: "climate.heating_circuit_1_patterilammitys",
                ATTR_TEMPERATURE: 22.0,
            },
            blocking=True,
        )

    mock_ouman_client.set_endpoint_value.assert_called_once_with(
        L1RoomSensor.ROOM_TEMPERATURE_SETPOINT_USER, 22
    )
