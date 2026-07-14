"""Tests for the Ouman EH-800 select platform."""

from unittest.mock import AsyncMock

from ouman_eh_800_api import (
    ControlEnum,
    EnumControlOumanEndpoint,
    HomeAwayControl,
    L1BaseEndpoints,
    OperationMode,
    OumanClientAuthenticationError,
    OumanClientCommunicationError,
    PumpSummerStopControl,
    RelayControl,
    RelayPumpSummerStop,
    RelayTemperature,
    SystemEndpoints,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import SCENARIOS

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize("scenario", SCENARIOS.keys(), indirect=True)
@pytest.mark.parametrize("init_integration", [Platform.SELECT], indirect=True)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the select entities for each registry-set scenario."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("init_integration", [Platform.SELECT], indirect=True)
@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("scenario", "entity_id", "endpoint", "initial_value", "target_value"),
    [
        pytest.param(
            "room_sensors",
            "select.ouman_eh_800_home_away_mode",
            SystemEndpoints.HOME_AWAY_MODE,
            HomeAwayControl.HOME,
            HomeAwayControl.AWAY,
            id="home_away_mode",
        ),
        pytest.param(
            "room_sensors",
            "select.heating_circuit_1_patterilammitys_operation_mode",
            L1BaseEndpoints.OPERATION_MODE,
            OperationMode.AUTOMATIC,
            OperationMode.SHUTDOWN,
            id="l1_operation_mode",
        ),
        pytest.param(
            "l1_constant_temp_relay_summer_stop",
            "select.ouman_eh_800_pump_summer_stop",
            RelayPumpSummerStop.CONTROL,
            PumpSummerStopControl.AUTO,
            PumpSummerStopControl.STOP,
            id="relay_pump_summer_stop",
        ),
        pytest.param(
            "relay_temperature",
            "select.ouman_eh_800_relay_control",
            RelayTemperature.CONTROL,
            RelayControl.AUTO,
            RelayControl.ON,
            id="relay_temperature",
        ),
    ],
    indirect=["scenario"],
)
async def test_async_select_option(
    hass: HomeAssistant,
    mock_ouman_client: AsyncMock,
    entity_id: str,
    endpoint: EnumControlOumanEndpoint,
    initial_value: ControlEnum,
    target_value: ControlEnum,
) -> None:
    """Test that selecting an option writes to the device and updates state."""
    assert hass.states.get(entity_id).state == initial_value.name.lower()

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: target_value.name.lower()},
        blocking=True,
    )

    mock_ouman_client.set_endpoint_value.assert_called_once_with(endpoint, target_value)
    assert hass.states.get(entity_id).state == target_value.name.lower()


@pytest.mark.parametrize("init_integration", [Platform.SELECT], indirect=True)
@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("client_error", "expected_exception", "expected_message"),
    [
        pytest.param(
            OumanClientAuthenticationError("Wrong username or password"),
            HomeAssistantError,
            "Authentication failed",
            id="auth_failure",
        ),
        pytest.param(
            OumanClientCommunicationError("Network error: Connection refused"),
            HomeAssistantError,
            "Error communicating with API",
            id="communication_failure",
        ),
    ],
)
async def test_async_select_option_errors(
    hass: HomeAssistant,
    mock_ouman_client: AsyncMock,
    client_error: Exception,
    expected_exception: type[Exception],
    expected_message: str,
) -> None:
    """Test that errors from the client are mapped to the expected exceptions."""
    mock_ouman_client.set_endpoint_value.side_effect = client_error

    with pytest.raises(expected_exception, match=expected_message):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.ouman_eh_800_home_away_mode",
                ATTR_OPTION: HomeAwayControl.AWAY.name.lower(),
            },
            blocking=True,
        )
