"""Tests for the Alexa Devices climate platform."""

from typing import Any
from unittest.mock import AsyncMock, call, patch

from aioamazondevices.exceptions import CannotSetFeature
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_MODE,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    HVACMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from . import setup_integration
from .const import TEST_DEVICE_THERMOSTAT, TEST_DEVICE_THERMOSTAT_SN

ENTITY_ID = "climate.thermostat_test"


@pytest.fixture(autouse=True)
def mock_thermostat_device(mock_amazon_devices_client: AsyncMock) -> None:
    """Return the thermostat as the only device."""
    mock_amazon_devices_client.get_devices_data.return_value = {
        TEST_DEVICE_THERMOSTAT_SN: TEST_DEVICE_THERMOSTAT
    }


@pytest.mark.usefixtures("mock_amazon_devices_client")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all entities."""
    with patch("homeassistant.components.alexa_devices.PLATFORMS", [Platform.CLIMATE]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("mode", "expected_attributes"),
    [
        pytest.param(
            "HEAT",
            {
                ATTR_TEMPERATURE: 62.0,
                ATTR_TARGET_TEMP_LOW: None,
                ATTR_TARGET_TEMP_HIGH: None,
                ATTR_MIN_TEMP: 40.0,
                ATTR_MAX_TEMP: 87.0,
            },
            id="heat",
        ),
        pytest.param(
            "COOL",
            {
                ATTR_TEMPERATURE: 62.0,
                ATTR_TARGET_TEMP_LOW: None,
                ATTR_TARGET_TEMP_HIGH: None,
                ATTR_MIN_TEMP: 43.0,
                ATTR_MAX_TEMP: 90.0,
            },
            id="cool",
        ),
        pytest.param(
            "AUTO",
            {
                ATTR_TEMPERATURE: None,
                ATTR_TARGET_TEMP_LOW: 65.0,
                ATTR_TARGET_TEMP_HIGH: 72.0,
                ATTR_MIN_TEMP: 40.0,
                ATTR_MAX_TEMP: 90.0,
            },
            id="auto",
        ),
        pytest.param(
            "ECO",
            {
                ATTR_TEMPERATURE: None,
                ATTR_TARGET_TEMP_LOW: 65.0,
                ATTR_TARGET_TEMP_HIGH: 72.0,
                ATTR_MIN_TEMP: 40.0,
                ATTR_MAX_TEMP: 90.0,
            },
            id="eco",
        ),
    ],
)
async def test_mode_state(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mode: str,
    expected_attributes: dict[str, Any],
) -> None:
    """Test the setpoints and limits shown in each mode."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    mock_amazon_devices_client.sensors[TEST_DEVICE_THERMOSTAT_SN][
        "thermostatMode"
    ].value = mode
    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 72.0
    assert {
        key: state.attributes.get(key) for key in expected_attributes
    } == expected_attributes


def _operation(operation: str, payload: dict[str, Any]) -> Any:
    """Return the expected call of a thermostat operation."""
    return call(
        TEST_DEVICE_THERMOSTAT, "thermostat", operation, command_payload=payload
    )


@pytest.mark.parametrize(
    ("mode", "service", "service_data", "expected_calls", "expected_state"),
    [
        pytest.param(
            "AUTO",
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.HEAT},
            [_operation("setThermostatMode", {"thermostatMode": "HEAT"})],
            (HVACMode.HEAT, {ATTR_TEMPERATURE: 16.7}),
            id="hvac_mode",
        ),
        pytest.param(
            "ECO",
            SERVICE_SET_HVAC_MODE,
            {ATTR_HVAC_MODE: HVACMode.HEAT_COOL},
            [_operation("setThermostatMode", {"thermostatMode": "AUTO"})],
            (HVACMode.HEAT_COOL, {ATTR_TARGET_TEMP_LOW: 18.3}),
            id="hvac_mode_heat_cool",
        ),
        pytest.param(
            "AUTO",
            SERVICE_TURN_OFF,
            {},
            [_operation("setThermostatMode", {"thermostatMode": "OFF"})],
            (HVACMode.OFF, {}),
            id="turn_off",
        ),
        pytest.param(
            "OFF",
            SERVICE_TURN_ON,
            {},
            [_operation("setThermostatMode", {"thermostatMode": "AUTO"})],
            (HVACMode.HEAT_COOL, {ATTR_TARGET_TEMP_LOW: 18.3}),
            id="turn_on",
        ),
        pytest.param(
            "HEAT",
            SERVICE_SET_TEMPERATURE,
            {ATTR_TEMPERATURE: 20},
            [
                _operation(
                    "setTargetSetpoint",
                    {"targetSetpoint": {"value": "68", "scale": "FAHRENHEIT"}},
                )
            ],
            (HVACMode.HEAT, {ATTR_TEMPERATURE: 20.0}),
            id="temperature",
        ),
        pytest.param(
            "AUTO",
            SERVICE_SET_TEMPERATURE,
            {ATTR_TARGET_TEMP_LOW: 18, ATTR_TARGET_TEMP_HIGH: 24},
            [
                _operation(
                    "setTargetSetpoint",
                    {
                        "lowerSetpoint": {"value": "64.4", "scale": "FAHRENHEIT"},
                        "upperSetpoint": {"value": "75.2", "scale": "FAHRENHEIT"},
                    },
                )
            ],
            (
                HVACMode.HEAT_COOL,
                {ATTR_TARGET_TEMP_LOW: 18.0, ATTR_TARGET_TEMP_HIGH: 24.0},
            ),
            id="temperature_range",
        ),
        pytest.param(
            "ECO",
            SERVICE_SET_TEMPERATURE,
            {ATTR_TARGET_TEMP_LOW: 18, ATTR_TARGET_TEMP_HIGH: 24},
            [
                _operation(
                    "setTargetSetpoint",
                    {
                        "lowerSetpoint": {"value": "64.4", "scale": "FAHRENHEIT"},
                        "upperSetpoint": {"value": "75.2", "scale": "FAHRENHEIT"},
                    },
                )
            ],
            (
                HVACMode.HEAT_COOL,
                {ATTR_TARGET_TEMP_LOW: 18.0, ATTR_TARGET_TEMP_HIGH: 24.0},
            ),
            id="temperature_range_eco",
        ),
    ],
)
async def test_climate_services(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mode: str,
    service: str,
    service_data: dict[str, Any],
    expected_calls: list[Any],
    expected_state: tuple[HVACMode, dict[str, float]],
) -> None:
    """Test climate services call the operation and store the new state."""
    mock_amazon_devices_client.sensors[TEST_DEVICE_THERMOSTAT_SN][
        "thermostatMode"
    ].value = mode
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID, **service_data},
        blocking=True,
    )

    assert (
        mock_amazon_devices_client.call_feature_operation.call_args_list
        == expected_calls
    )
    expected_mode, expected_attributes = expected_state
    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == expected_mode
    assert {
        key: state.attributes.get(key) for key in expected_attributes
    } == expected_attributes


@pytest.mark.parametrize(
    ("mode", "service_data", "translation_key"),
    [
        pytest.param(
            "AUTO",
            {ATTR_TEMPERATURE: 20},
            "missing_target_temperature_entity_feature",
            id="temperature_in_heat_cool",
        ),
        pytest.param(
            "COOL",
            {ATTR_HVAC_MODE: HVACMode.HEAT, ATTR_TEMPERATURE: 20},
            "hvac_mode_with_temperature",
            id="hvac_mode_with_temperature",
        ),
        pytest.param(
            "AUTO",
            {
                ATTR_HVAC_MODE: HVACMode.HEAT_COOL,
                ATTR_TARGET_TEMP_LOW: 18,
                ATTR_TARGET_TEMP_HIGH: 24,
            },
            "hvac_mode_with_temperature",
            id="hvac_mode_with_temperature_range",
        ),
    ],
)
async def test_set_temperature_rejected(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mode: str,
    service_data: dict[str, Any],
    translation_key: str,
) -> None:
    """Test invalid target temperature requests are rejected."""
    mock_amazon_devices_client.sensors[TEST_DEVICE_THERMOSTAT_SN][
        "thermostatMode"
    ].value = mode
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: ENTITY_ID, **service_data},
            blocking=True,
        )

    assert exc_info.value.translation_key == translation_key
    mock_amazon_devices_client.call_feature_operation.assert_not_called()


async def test_command_without_known_setpoint(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a command is sent even when its setpoint was never reported."""
    sensors = mock_amazon_devices_client.sensors[TEST_DEVICE_THERMOSTAT_SN]
    sensors["thermostatMode"].value = "HEAT"
    del sensors["targetSetpoint"]
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 20},
        blocking=True,
    )

    mock_amazon_devices_client.call_feature_operation.assert_called_once()
    assert (state := hass.states.get(ENTITY_ID))
    assert state.attributes[ATTR_TEMPERATURE] is None


async def test_celsius_thermostat(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a thermostat using Celsius sends setpoints in Celsius."""
    sensors = mock_amazon_devices_client.sensors[TEST_DEVICE_THERMOSTAT_SN]
    for sensor in sensors.values():
        sensor.scale = "CELSIUS" if sensor.scale else None
    sensors["thermostatMode"].value = "HEAT"
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: 21.5},
        blocking=True,
    )

    mock_amazon_devices_client.call_feature_operation.assert_called_once_with(
        TEST_DEVICE_THERMOSTAT,
        "thermostat",
        "setTargetSetpoint",
        command_payload={"targetSetpoint": {"value": "21.5", "scale": "CELSIUS"}},
    )


async def test_pushed_sensor_update(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the thermostat reflects sensor values pushed by the Amazon API."""
    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == HVACMode.HEAT_COOL

    mock_amazon_devices_client.sensors[TEST_DEVICE_THERMOSTAT_SN][
        "thermostatMode"
    ].value = "OFF"
    event_handler = mock_amazon_devices_client.on_sensor_event.append.call_args.args[0]
    await event_handler()
    await hass.async_block_till_done()

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == HVACMode.OFF


async def test_unknown_state(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the thermostat state is unknown when its sensors are missing."""
    mock_amazon_devices_client.sensors[TEST_DEVICE_THERMOSTAT_SN] = {}
    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] is None


async def test_feature_operation_error(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a failed feature operation raises an error."""
    await setup_integration(hass, mock_config_entry)

    mock_amazon_devices_client.call_feature_operation.side_effect = CannotSetFeature(
        "rejected"
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_HVAC_MODE: HVACMode.COOL},
            blocking=True,
        )

    assert exc_info.value.translation_key == "cannot_set_feature_with_error"


async def test_partial_state(
    hass: HomeAssistant,
    mock_amazon_devices_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setpoints are unset when only the mode is known."""
    sensors = mock_amazon_devices_client.sensors[TEST_DEVICE_THERMOSTAT_SN]
    mock_amazon_devices_client.sensors[TEST_DEVICE_THERMOSTAT_SN] = {
        "thermostatMode": sensors["thermostatMode"]
    }
    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == HVACMode.HEAT_COOL
    assert state.attributes[ATTR_TARGET_TEMP_LOW] is None
    assert state.attributes[ATTR_TARGET_TEMP_HIGH] is None
