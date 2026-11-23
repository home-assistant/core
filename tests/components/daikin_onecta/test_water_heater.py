"""Tests for Daikin Onecta water heater entities."""

from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock, call

from daikin_onecta.exceptions import OnectaConnectionError
from daikin_onecta.models import GatewayDevice, ManagementPoint
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.daikin_onecta.const import DOMAIN
from homeassistant.components.daikin_onecta.water_heater import DaikinWaterTank
from homeassistant.components.water_heater import (
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DOMAIN as WATER_HEATER_DOMAIN,
    SERVICE_SET_OPERATION_MODE as WATER_HEATER_SERVICE_SET_OPERATION_MODE,
    SERVICE_SET_TEMPERATURE as WATER_HEATER_SERVICE_SET_TEMPERATURE,
    SERVICE_TURN_OFF as WATER_HEATER_SERVICE_TURN_OFF,
    SERVICE_TURN_ON as WATER_HEATER_SERVICE_TURN_ON,
    STATE_HEAT_PUMP,
    STATE_OFF,
    STATE_PERFORMANCE,
    WaterHeaterEntityFeature,
    WaterHeaterServiceArgument,
    WaterHeaterStateAttribute,
)
from homeassistant.const import ATTR_ENTITY_ID, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.util.unit_conversion import TemperatureConverter
from homeassistant.util.unit_system import (
    METRIC_SYSTEM,
    US_CUSTOMARY_SYSTEM,
    UnitSystem,
)

from .conftest import MockOnectaClient
from .platform_helpers import (
    ALTHERMA_WATER_HEATER_ENTITY_ID,
    _async_setup_fixture,
    _execute_typed_command,
    _load_gateway_devices,
)


@pytest.mark.parametrize(
    ("gateway_name_by_user", "expected_gateway_name"),
    [
        pytest.param(None, "Altherma", id="default-gateway-name"),
        pytest.param("Renamed Altherma", "Renamed Altherma", id="renamed-gateway"),
    ],
)
async def test_water_heater_error_uses_gateway_and_point_names(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    mock_onecta_client: MockOnectaClient,
    gateway_name_by_user: str | None,
    expected_gateway_name: str,
) -> None:
    """Include the gateway name when reporting an unnamed physical point."""
    gateway = _load_gateway_devices("altherma")[0]
    await _async_setup_fixture(
        hass, config_entry, "altherma", gateway_devices=[gateway]
    )
    gateway_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, gateway.id), config_entry.entry_id
    )
    assert gateway_entry is not None
    device_registry.async_update_device(
        gateway_entry.id, name_by_user=gateway_name_by_user
    )
    mock_onecta_client.patch_characteristic.side_effect = OnectaConnectionError(
        "test connection failure", method="PATCH", path="/test"
    )

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            WATER_HEATER_SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: ALTHERMA_WATER_HEATER_ENTITY_ID,
                WaterHeaterServiceArgument.TEMPERATURE: 50,
            },
            blocking=True,
        )

    assert err.value.translation_placeholders == {
        "device": f"{expected_gateway_name} Domestic hot water tank"
    }


async def _async_setup_water_tank(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fixture: str,
    gateway_devices: list[GatewayDevice],
    embedded_id: str,
) -> DaikinWaterTank:
    """Set up a water tank with the real integration coordinator."""
    await _async_setup_fixture(
        hass, config_entry, fixture, gateway_devices=gateway_devices
    )
    coordinator = config_entry.runtime_data
    device = coordinator.data[gateway_devices[0].id]
    return DaikinWaterTank(device, coordinator, embedded_id)


@pytest.mark.parametrize(
    ("power_settable", "expected_features", "expected_operation_list"),
    [
        pytest.param(
            False,
            WaterHeaterEntityFeature(0),
            [STATE_HEAT_PUMP],
            id="read-only",
        ),
        pytest.param(
            True,
            WaterHeaterEntityFeature.ON_OFF | WaterHeaterEntityFeature.OPERATION_MODE,
            ["off", STATE_HEAT_PUMP],
            id="writable",
        ),
    ],
)
async def test_water_heater_features_follow_power_capability(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    power_settable: bool,
    expected_features: WaterHeaterEntityFeature,
    expected_operation_list: list[str],
) -> None:
    """Only advertise power and operation controls for a writable characteristic."""
    gateway_devices = _load_gateway_devices("holidaymode")
    point = gateway_devices[0].management_points_by_type("domesticHotWaterFlowThrough")[
        0
    ]
    point.on_off_mode.settable = power_settable
    entity = await _async_setup_water_tank(
        hass, config_entry, "holidaymode", gateway_devices, point.embedded_id
    )
    assert entity.supported_features == expected_features
    assert entity.operation_list == expected_operation_list


@pytest.mark.parametrize(
    ("service", "power_value", "service_data"),
    [
        pytest.param(WATER_HEATER_SERVICE_TURN_ON, "off", {}, id="turn-on"),
        pytest.param(WATER_HEATER_SERVICE_TURN_OFF, "on", {}, id="turn-off"),
        pytest.param(
            WATER_HEATER_SERVICE_SET_OPERATION_MODE,
            "on",
            {WaterHeaterServiceArgument.OPERATION_MODE: STATE_OFF},
            id="operation-mode",
        ),
    ],
)
async def test_water_heater_rejects_read_only_power(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
    service: str,
    power_value: str,
    service_data: dict[str, str],
) -> None:
    """Read-only water-heater actions fail without spending a cloud request."""
    await _async_setup_fixture(hass, config_entry, "holidaymode")
    coordinator = config_entry.runtime_data
    device = next(iter(coordinator.data.values()))
    point = device.device.management_points_by_type("domesticHotWaterFlowThrough")[0]
    assert point.on_off_mode is not None
    point.on_off_mode.value = power_value
    point.on_off_mode.settable = False
    coordinator.async_update_listeners()
    entity_id = hass.states.async_entity_ids(WATER_HEATER_DOMAIN)[0]

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id, **service_data},
            blocking=True,
        )

    mock_onecta_client.patch_characteristic.assert_not_awaited()


@pytest.mark.parametrize(
    ("power", "expected_features", "expected_operation_list"),
    [
        pytest.param(
            "on",
            WaterHeaterEntityFeature.TARGET_TEMPERATURE
            | WaterHeaterEntityFeature.OPERATION_MODE,
            [STATE_HEAT_PUMP, STATE_PERFORMANCE],
            id="on",
        ),
        pytest.param(
            "off",
            WaterHeaterEntityFeature.TARGET_TEMPERATURE,
            [STATE_OFF],
            id="off",
        ),
    ],
)
async def test_water_heater_read_only_power_keeps_writable_boost(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    power: str,
    expected_features: WaterHeaterEntityFeature,
    expected_operation_list: list[str],
) -> None:
    """Allow writable boost while powered on without advertising power control."""
    gateway_devices = _load_gateway_devices("altherma_boost")
    point = gateway_devices[0].management_points_by_type("domesticHotWaterTank")[0]
    point.on_off_mode.settable = False
    point.on_off_mode.value = power
    entity = await _async_setup_water_tank(
        hass, config_entry, "altherma_boost", gateway_devices, point.embedded_id
    )
    assert entity.supported_features == expected_features
    assert entity.operation_list == expected_operation_list


async def test_water_heater_initial_state_includes_read_only_current_operation(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Include the active operation when power and boost are read-only."""
    gateway_devices = _load_gateway_devices("altherma_boost")
    point = gateway_devices[0].management_points_by_type("domesticHotWaterTank")[0]
    assert point.domestic_hot_water is not None
    assert point.domestic_hot_water.power is not None
    assert point.domestic_hot_water.powerful_mode is not None
    point.domestic_hot_water.power.value = "on"
    point.domestic_hot_water.power.settable = False
    point.domestic_hot_water.powerful_mode.value = "on"
    point.domestic_hot_water.powerful_mode.settable = False

    entity = await _async_setup_water_tank(
        hass, config_entry, "altherma_boost", gateway_devices, point.embedded_id
    )
    assert entity.current_operation == STATE_PERFORMANCE
    assert entity.operation_list == [STATE_PERFORMANCE]
    assert not entity.supported_features & WaterHeaterEntityFeature.OPERATION_MODE


async def test_water_heater_handles_missing_temperature_values(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Restore HA defaults when Daikin stops reporting temperature bounds."""
    gateway_devices = _load_gateway_devices("altherma_boost")
    point = gateway_devices[0].management_points_by_type("domesticHotWaterTank")[0]
    assert point.domestic_hot_water is not None
    assert point.domestic_hot_water.temperature is not None
    point.domestic_hot_water.temperature.min_value = 45
    point.domestic_hot_water.temperature.max_value = 60
    entity = await _async_setup_water_tank(
        hass, config_entry, "altherma_boost", gateway_devices, point.embedded_id
    )
    assert entity.min_temp == 45
    assert entity.max_temp == 60
    coordinator = config_entry.runtime_data
    device = coordinator.data[gateway_devices[0].id]
    current_point = device.management_point(point.embedded_id)
    assert current_point is not None
    assert current_point.domestic_hot_water is not None
    assert current_point.domestic_hot_water.temperature is not None
    current_point.domestic_hot_water.temperature.value = None
    current_point.domestic_hot_water.temperature.min_value = None
    current_point.domestic_hot_water.temperature.max_value = None
    entity.update_state()

    assert entity.target_temperature is None
    assert entity.min_temp == TemperatureConverter.convert(
        DEFAULT_MIN_TEMP, UnitOfTemperature.FAHRENHEIT, entity.native_temperature_unit
    )
    assert entity.max_temp == TemperatureConverter.convert(
        DEFAULT_MAX_TEMP, UnitOfTemperature.FAHRENHEIT, entity.native_temperature_unit
    )


@pytest.mark.parametrize(
    ("setpoint_unit", "sensory_unit", "expected_unit"),
    [
        ("°F", None, UnitOfTemperature.FAHRENHEIT),
        (None, "°F", UnitOfTemperature.FAHRENHEIT),
        (None, None, UnitOfTemperature.CELSIUS),
        ("C", None, UnitOfTemperature.CELSIUS),
    ],
)
async def test_water_heater_uses_daikin_temperature_unit(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    setpoint_unit: str | None,
    sensory_unit: str | None,
    expected_unit: UnitOfTemperature,
) -> None:
    """Use the reported setpoint or tank-sensor unit, defaulting to Celsius."""
    gateway_devices = _load_gateway_devices("altherma_boost")
    point = gateway_devices[0].management_points_by_type("domesticHotWaterTank")[0]
    setpoint = point.domestic_hot_water.temperature
    tank_temperature = point.sensory_characteristic("tankTemperature")
    assert setpoint is not None
    assert tank_temperature is not None
    setpoint.unit = setpoint_unit
    tank_temperature.unit = sensory_unit

    entity = await _async_setup_water_tank(
        hass, config_entry, "altherma_boost", gateway_devices, point.embedded_id
    )

    assert entity.native_temperature_unit == expected_unit


@pytest.mark.parametrize(
    ("step_value", "expected_step"),
    [(None, 1.0), (0.5, 0.5)],
)
async def test_water_heater_uses_standard_target_temperature_step(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    step_value: float | None,
    expected_step: float,
) -> None:
    """Expose the Daikin increment or the whole-degree fallback."""
    gateway_devices = _load_gateway_devices("altherma_boost")
    point = gateway_devices[0].management_points_by_type("domesticHotWaterTank")[0]
    assert point.domestic_hot_water is not None
    assert point.domestic_hot_water.temperature is not None
    point.domestic_hot_water.temperature.step_value = step_value

    entity = await _async_setup_water_tank(
        hass, config_entry, "altherma_boost", gateway_devices, point.embedded_id
    )
    assert entity.target_temperature_step == expected_step


def _leave_temperature_control_writable(point: ManagementPoint) -> None:
    """Leave the tank temperature characteristic writable."""


def _make_temperature_control_read_only(point: ManagementPoint) -> None:
    """Make the tank temperature characteristic read-only."""
    assert point.domestic_hot_water is not None
    assert point.domestic_hot_water.temperature is not None
    point.domestic_hot_water.temperature.settable = False


def _remove_temperature_control(point: ManagementPoint) -> None:
    """Remove the tank setpoint characteristic."""
    point.temperature_control.value.operation_modes["heating"].setpoints.pop(
        "domesticHotWaterTemperature"
    )


@pytest.mark.parametrize(
    ("power_value", "change_control", "translation_key"),
    [
        pytest.param(
            "off", _leave_temperature_control_writable, "water_heater_off", id="off"
        ),
        pytest.param(
            "on",
            _make_temperature_control_read_only,
            "service_not_supported",
            id="read-only",
        ),
        pytest.param(
            "on", _remove_temperature_control, "service_not_supported", id="missing"
        ),
    ],
)
async def test_water_heater_rejects_unavailable_temperature_control(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    power_value: str,
    change_control: Callable[[ManagementPoint], None],
    translation_key: str,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Reject a HA temperature request when its device control is unavailable."""
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    coordinator = config_entry.runtime_data
    execute = _execute_typed_command(config_entry, mock_onecta_client)
    coordinator.async_execute_command = execute
    gateway = next(iter(coordinator.data.values()))
    point = gateway.device.management_points_by_type("domesticHotWaterTank")[0]
    point.on_off_mode.value = power_value
    change_control(point)
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            WATER_HEATER_SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: ALTHERMA_WATER_HEATER_ENTITY_ID,
                WaterHeaterServiceArgument.TEMPERATURE: 50,
            },
            blocking=True,
        )

    assert err.value.translation_key == translation_key
    execute.assert_not_awaited()


@pytest.mark.parametrize(
    ("power_value", "service"),
    [
        ("off", WATER_HEATER_SERVICE_TURN_ON),
        ("on", WATER_HEATER_SERVICE_TURN_OFF),
    ],
)
async def test_water_heater_rejects_unavailable_power_control(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    power_value: str,
    service: str,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Reject unsupported power actions through Home Assistant services."""
    await _async_setup_fixture(hass, config_entry, "holidaymode")
    coordinator = config_entry.runtime_data
    execute = _execute_typed_command(config_entry, mock_onecta_client)
    coordinator.async_execute_command = execute
    point = next(
        point
        for device in coordinator.data.values()
        for point in device.device.management_points
        if point.management_point_type == "domesticHotWaterFlowThrough"
    )
    point.on_off_mode.value = power_value
    point.on_off_mode.settable = False
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    state = hass.states.async_all(WATER_HEATER_DOMAIN)[0]
    assert state is not None
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            service,
            {ATTR_ENTITY_ID: state.entity_id},
            blocking=True,
        )

    assert err.value.translation_key == "service_not_supported"
    execute.assert_not_awaited()


async def test_water_heater_rejects_unadvertised_operation_mode(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Reject an operation mode through HA that Daikin does not advertise."""
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    execute = _execute_typed_command(config_entry, mock_onecta_client)
    config_entry.runtime_data.async_execute_command = execute

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            WATER_HEATER_SERVICE_SET_OPERATION_MODE,
            {
                ATTR_ENTITY_ID: ALTHERMA_WATER_HEATER_ENTITY_ID,
                "operation_mode": "unsupported_mode",
            },
            blocking=True,
        )

    execute.assert_not_awaited()


async def test_water_heater_rejects_heat_pump_with_read_only_performance_mode(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Do not report success if read-only boost prevents heat-pump mode."""
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    coordinator = config_entry.runtime_data
    execute = _execute_typed_command(config_entry, mock_onecta_client)
    coordinator.async_execute_command = execute
    point = next(
        point
        for device in coordinator.data.values()
        for point in device.device.management_points
        if point.management_point_type == "domesticHotWaterTank"
    )
    assert point.domestic_hot_water is not None
    powerful_mode = point.domestic_hot_water.powerful_mode
    assert powerful_mode is not None
    powerful_mode.value = "on"
    powerful_mode.settable = False
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    entity = hass.data[WATER_HEATER_DOMAIN].get_entity(ALTHERMA_WATER_HEATER_ENTITY_ID)
    assert isinstance(entity, DaikinWaterTank)
    assert STATE_HEAT_PUMP not in entity.operation_list
    assert STATE_PERFORMANCE in entity.operation_list

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        WATER_HEATER_SERVICE_SET_OPERATION_MODE,
        {
            ATTR_ENTITY_ID: ALTHERMA_WATER_HEATER_ENTITY_ID,
            "operation_mode": STATE_PERFORMANCE,
        },
        blocking=True,
    )

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            WATER_HEATER_SERVICE_SET_OPERATION_MODE,
            {
                ATTR_ENTITY_ID: ALTHERMA_WATER_HEATER_ENTITY_ID,
                "operation_mode": STATE_HEAT_PUMP,
            },
            blocking=True,
        )

    assert err.value.translation_key == "not_valid_operation_mode"
    execute.assert_not_awaited()


async def test_water_heater_turn_off_updates_cached_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """A successful water-heater command updates the cached operation mode."""
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    config_entry.runtime_data.async_execute_command = _execute_typed_command(
        config_entry, mock_onecta_client
    )
    listener = MagicMock()
    remove_listener = config_entry.runtime_data.async_add_listener(listener)

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        WATER_HEATER_SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ALTHERMA_WATER_HEATER_ENTITY_ID},
        blocking=True,
    )

    state = hass.states.get(ALTHERMA_WATER_HEATER_ENTITY_ID)
    assert state is not None
    assert state.attributes[WaterHeaterStateAttribute.OPERATION_MODE] == "off"

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        WATER_HEATER_SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: state.entity_id},
        blocking=True,
    )
    state = hass.states.get(state.entity_id)
    assert state is not None
    assert (
        state.attributes[WaterHeaterStateAttribute.OPERATION_MODE] == STATE_PERFORMANCE
    )
    assert listener.call_count == 2
    remove_listener()


async def test_water_heater_temperature_updates_typed_cache(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """A successful temperature write updates the shared typed model."""
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    config_entry.runtime_data.async_execute_command = _execute_typed_command(
        config_entry, mock_onecta_client
    )
    listener = MagicMock()
    remove_listener = config_entry.runtime_data.async_add_listener(listener)

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        WATER_HEATER_SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: ALTHERMA_WATER_HEATER_ENTITY_ID,
            WaterHeaterServiceArgument.TEMPERATURE: 50,
        },
        blocking=True,
    )

    management_point = next(
        point
        for device in config_entry.runtime_data.data.values()
        for point in device.device.management_points
        if point.management_point_type == "domesticHotWaterTank"
    )
    assert management_point.domestic_hot_water is not None
    assert management_point.domestic_hot_water.temperature is not None
    assert management_point.domestic_hot_water.temperature.value == 50
    listener.assert_called_once()
    remove_listener()


async def test_water_heater_set_temperature_applies_operation_mode_first(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Apply a non-off mode before a combined temperature write."""
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    coordinator = config_entry.runtime_data
    coordinator.async_execute_command = _execute_typed_command(
        config_entry, mock_onecta_client
    )
    gateway = next(iter(coordinator.data.values()))
    point = gateway.device.management_points_by_type("domesticHotWaterTank")[0]
    assert point.domestic_hot_water is not None
    assert point.domestic_hot_water.powerful_mode is not None
    assert point.domestic_hot_water.temperature is not None
    point.on_off_mode.value = "on"
    point.domestic_hot_water.powerful_mode.value = "on"
    point.domestic_hot_water.temperature.value = 45
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        WATER_HEATER_SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: ALTHERMA_WATER_HEATER_ENTITY_ID,
            WaterHeaterServiceArgument.OPERATION_MODE: STATE_HEAT_PUMP,
            WaterHeaterServiceArgument.TEMPERATURE: 50,
        },
        blocking=True,
    )

    assert mock_onecta_client.patch_characteristic.await_args_list == [
        call(gateway.id, point.embedded_id, "powerfulMode", "off", path=None),
        call(
            gateway.id,
            point.embedded_id,
            "temperatureControl",
            50,
            path="/operationModes/heating/setpoints/domesticHotWaterTemperature",
        ),
    ]


async def test_water_heater_set_temperature_applies_temperature_before_off(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Write the target temperature before turning the tank off."""
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    coordinator = config_entry.runtime_data
    coordinator.async_execute_command = _execute_typed_command(
        config_entry, mock_onecta_client
    )
    gateway = next(iter(coordinator.data.values()))
    point = gateway.device.management_points_by_type("domesticHotWaterTank")[0]
    point.on_off_mode.value = "on"
    assert point.domestic_hot_water is not None
    assert point.domestic_hot_water.temperature is not None
    point.domestic_hot_water.temperature.value = 45
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        WATER_HEATER_SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: ALTHERMA_WATER_HEATER_ENTITY_ID,
            WaterHeaterServiceArgument.OPERATION_MODE: STATE_OFF,
            WaterHeaterServiceArgument.TEMPERATURE: 50,
        },
        blocking=True,
    )

    assert mock_onecta_client.patch_characteristic.await_args_list == [
        call(
            gateway.id,
            point.embedded_id,
            "temperatureControl",
            50,
            path="/operationModes/heating/setpoints/domesticHotWaterTemperature",
        ),
        call(gateway.id, point.embedded_id, "onOffMode", "off", path=None),
    ]


async def test_water_heater_rejects_temperature_when_off_target_is_off(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Do not write the temperature when the heater is already off."""
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    coordinator = config_entry.runtime_data
    execute = _execute_typed_command(config_entry, mock_onecta_client)
    coordinator.async_execute_command = execute
    gateway = next(iter(coordinator.data.values()))
    point = gateway.device.management_points_by_type("domesticHotWaterTank")[0]
    assert point.domestic_hot_water is not None
    assert point.domestic_hot_water.temperature is not None
    point.on_off_mode.value = "off"
    point.domestic_hot_water.temperature.value = 45
    point.domestic_hot_water.temperature.settable = True
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            WATER_HEATER_SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: ALTHERMA_WATER_HEATER_ENTITY_ID,
                WaterHeaterServiceArgument.OPERATION_MODE: STATE_OFF,
                WaterHeaterServiceArgument.TEMPERATURE: 50,
            },
            blocking=True,
        )

    assert err.value.translation_key == "water_heater_off"
    execute.assert_not_awaited()


async def test_water_heater_rejects_invalid_combined_mode_before_temperature_write(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Validate the requested mode before writing a combined temperature."""
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    coordinator = config_entry.runtime_data
    execute = _execute_typed_command(config_entry, mock_onecta_client)
    coordinator.async_execute_command = execute

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            WATER_HEATER_SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: ALTHERMA_WATER_HEATER_ENTITY_ID,
                WaterHeaterServiceArgument.OPERATION_MODE: "unsupported_mode",
                WaterHeaterServiceArgument.TEMPERATURE: 50,
            },
            blocking=True,
        )

    execute.assert_not_awaited()


async def test_water_heater_temperature_writes_without_power_characteristic(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """A settable temperature remains usable without on/off control."""
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    coordinator = config_entry.runtime_data
    execute = _execute_typed_command(config_entry, mock_onecta_client)
    coordinator.async_execute_command = execute
    gateway = next(iter(coordinator.data.values()))
    point = gateway.device.management_points_by_type("domesticHotWaterTank")[0]
    point.on_off_mode = None
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        WATER_HEATER_SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: ALTHERMA_WATER_HEATER_ENTITY_ID,
            WaterHeaterServiceArgument.TEMPERATURE: 50,
        },
        blocking=True,
    )

    assert point.domestic_hot_water is not None
    assert point.domestic_hot_water.temperature is not None
    assert point.domestic_hot_water.temperature.value == 50
    mock_onecta_client.patch_characteristic.assert_awaited_once_with(
        gateway.id,
        point.embedded_id,
        "temperatureControl",
        50,
        path="/operationModes/heating/setpoints/domesticHotWaterTemperature",
    )


@pytest.mark.parametrize(
    ("unit_system", "service_temperature", "step_value", "expected_temperature"),
    [
        (METRIC_SYSTEM, 48.6, 1, 49),
        (US_CUSTOMARY_SYSTEM, 120, 1, 49),
        (METRIC_SYSTEM, 48.6, 0.5, 48.5),
        (METRIC_SYSTEM, 49.2, 2, 50),
        (METRIC_SYSTEM, 45.3, 0.1, 45.3),
        (METRIC_SYSTEM, 48.6, None, 49),
        (METRIC_SYSTEM, 44.25, None, 44),
    ],
)
async def test_water_heater_temperature_rounds_to_native_step(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    unit_system: UnitSystem,
    service_temperature: float,
    step_value: float | None,
    expected_temperature: float,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Round requested temperatures to the nearest supported native step."""
    hass.config.units = unit_system
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    coordinator = config_entry.runtime_data
    execute = _execute_typed_command(config_entry, mock_onecta_client)
    coordinator.async_execute_command = execute
    gateway = next(iter(coordinator.data.values()))
    point = gateway.device.management_points_by_type("domesticHotWaterTank")[0]
    assert point.domestic_hot_water is not None
    assert point.domestic_hot_water.temperature is not None
    point.domestic_hot_water.temperature.step_value = step_value

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        WATER_HEATER_SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: ALTHERMA_WATER_HEATER_ENTITY_ID,
            WaterHeaterServiceArgument.TEMPERATURE: service_temperature,
        },
        blocking=True,
    )

    assert point.domestic_hot_water.temperature.value == expected_temperature
    mock_onecta_client.patch_characteristic.assert_awaited_once_with(
        gateway.id,
        point.embedded_id,
        "temperatureControl",
        expected_temperature,
        path="/operationModes/heating/setpoints/domesticHotWaterTemperature",
    )


async def test_water_heater_rounded_current_temperature_does_not_write(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Skip a request when the rounded target equals the current tank target."""
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    coordinator = config_entry.runtime_data
    coordinator.async_execute_command = _execute_typed_command(
        config_entry, mock_onecta_client
    )
    point = next(
        point
        for device in coordinator.data.values()
        for point in device.device.management_points
        if point.management_point_type == "domesticHotWaterTank"
    )
    assert point.domestic_hot_water is not None
    assert point.domestic_hot_water.temperature is not None
    point.domestic_hot_water.temperature.value = 48
    point.domestic_hot_water.temperature.step_value = 1
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        WATER_HEATER_SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: ALTHERMA_WATER_HEATER_ENTITY_ID,
            WaterHeaterServiceArgument.TEMPERATURE: 48.4,
        },
        blocking=True,
    )

    mock_onecta_client.patch_characteristic.assert_not_awaited()


@pytest.mark.parametrize(
    ("minimum", "maximum", "step", "requested", "expected"),
    [
        pytest.param(43.3, 60, 0.5, 44, 43.8, id="round-from-minimum"),
        pytest.param(43, 60, 0.5, 70, 60, id="clamp-to-maximum"),
    ],
)
async def test_water_heater_temperature_is_rounded_and_clamped(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    minimum: float,
    maximum: float,
    step: float,
    requested: float,
    expected: float,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Round relative to the minimum and clamp to Daikin's setpoint bounds."""
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    coordinator = config_entry.runtime_data
    coordinator.async_execute_command = _execute_typed_command(
        config_entry, mock_onecta_client
    )
    gateway = next(iter(coordinator.data.values()))
    point = gateway.device.management_points_by_type("domesticHotWaterTank")[0]
    assert point.domestic_hot_water is not None
    setpoint = point.domestic_hot_water.temperature
    assert setpoint is not None
    setpoint.min_value = minimum
    setpoint.max_value = maximum
    setpoint.step_value = step

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        WATER_HEATER_SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: ALTHERMA_WATER_HEATER_ENTITY_ID,
            WaterHeaterServiceArgument.TEMPERATURE: requested,
        },
        blocking=True,
    )

    assert setpoint.value == expected
    mock_onecta_client.patch_characteristic.assert_awaited_once_with(
        gateway.id,
        point.embedded_id,
        "temperatureControl",
        expected,
        path="/operationModes/heating/setpoints/domesticHotWaterTemperature",
    )


@pytest.mark.parametrize(
    ("requested", "expected"),
    [
        pytest.param(40, 44, id="lower-default-bound"),
        pytest.param(80, 60, id="upper-default-bound"),
    ],
)
async def test_water_heater_clamps_to_ha_defaults_without_daikin_limits(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
    requested: float,
    expected: float,
) -> None:
    """Clamp targets to the limits advertised when Daikin omits tank limits."""
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    coordinator = config_entry.runtime_data
    coordinator.async_execute_command = _execute_typed_command(
        config_entry, mock_onecta_client
    )
    gateway = next(iter(coordinator.data.values()))
    point = gateway.device.management_points_by_type("domesticHotWaterTank")[0]
    assert point.domestic_hot_water is not None
    setpoint = point.domestic_hot_water.temperature
    assert setpoint is not None
    setpoint.min_value = None
    setpoint.max_value = None
    setpoint.value = 45
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        WATER_HEATER_SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: ALTHERMA_WATER_HEATER_ENTITY_ID,
            WaterHeaterServiceArgument.TEMPERATURE: requested,
        },
        blocking=True,
    )

    assert setpoint.value == expected
    mock_onecta_client.patch_characteristic.assert_awaited_once_with(
        gateway.id,
        point.embedded_id,
        "temperatureControl",
        expected,
        path="/operationModes/heating/setpoints/domesticHotWaterTemperature",
    )


async def test_water_heater_publishes_successful_partial_operation_write(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Keep a successful power stage visible when the boost stage fails."""
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    coordinator = config_entry.runtime_data
    point = next(
        point
        for device in coordinator.data.values()
        for point in device.device.management_points
        if point.management_point_type == "domesticHotWaterTank"
    )
    point.on_off_mode.value = "off"
    assert point.domestic_hot_water is not None
    assert point.domestic_hot_water.powerful_mode is not None
    point.domestic_hot_water.powerful_mode.value = "off"
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    coordinator.async_execute_command = AsyncMock(side_effect=[True, False])
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            WATER_HEATER_SERVICE_SET_OPERATION_MODE,
            {
                ATTR_ENTITY_ID: ALTHERMA_WATER_HEATER_ENTITY_ID,
                "operation_mode": STATE_PERFORMANCE,
            },
            blocking=True,
        )

    state = hass.states.get(ALTHERMA_WATER_HEATER_ENTITY_ID)
    assert state is not None
    assert state.attributes[WaterHeaterStateAttribute.OPERATION_MODE] == STATE_HEAT_PUMP
    assert coordinator.async_execute_command.await_count == 2


@pytest.mark.parametrize(
    ("service", "service_data", "power_value"),
    [
        (WATER_HEATER_SERVICE_TURN_ON, {}, None),
        (WATER_HEATER_SERVICE_TURN_OFF, {}, None),
        (
            WATER_HEATER_SERVICE_SET_OPERATION_MODE,
            {"operation_mode": STATE_HEAT_PUMP},
            None,
        ),
        (
            WATER_HEATER_SERVICE_SET_TEMPERATURE,
            {WaterHeaterServiceArgument.TEMPERATURE: 50},
            None,
        ),
        (
            WATER_HEATER_SERVICE_SET_TEMPERATURE,
            {WaterHeaterServiceArgument.TEMPERATURE: 50},
            "unknown",
        ),
    ],
)
async def test_water_heater_rejects_unknown_power_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    service: str,
    service_data: dict[str, str | int],
    power_value: str | None,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Reject HA write services when Daikin omits the current power value."""
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    coordinator = config_entry.runtime_data
    execute = _execute_typed_command(config_entry, mock_onecta_client)
    coordinator.async_execute_command = execute
    point = next(
        point
        for device in coordinator.data.values()
        for point in device.device.management_points
        if point.management_point_type == "domesticHotWaterTank"
    )
    point.on_off_mode.value = power_value
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            service,
            {
                ATTR_ENTITY_ID: ALTHERMA_WATER_HEATER_ENTITY_ID,
                **service_data,
            },
            blocking=True,
        )

    assert err.value.translation_key == "water_heater_on_off_unavailable"
    execute.assert_not_awaited()


async def test_water_heater_set_performance_updates_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """A successful boost command updates the entity through HA's service API."""
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    execute = _execute_typed_command(config_entry, mock_onecta_client)
    config_entry.runtime_data.async_execute_command = execute
    point = next(
        point
        for device in config_entry.runtime_data.data.values()
        for point in device.device.management_points
        if point.management_point_type == "domesticHotWaterTank"
    )
    assert point.domestic_hot_water is not None
    assert point.domestic_hot_water.powerful_mode is not None
    point.domestic_hot_water.powerful_mode.value = "off"
    config_entry.runtime_data.async_update_listeners()
    await hass.async_block_till_done()

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        WATER_HEATER_SERVICE_SET_OPERATION_MODE,
        {
            ATTR_ENTITY_ID: ALTHERMA_WATER_HEATER_ENTITY_ID,
            "operation_mode": STATE_PERFORMANCE,
        },
        blocking=True,
    )

    state = hass.states.get(ALTHERMA_WATER_HEATER_ENTITY_ID)
    assert state is not None
    assert (
        state.attributes[WaterHeaterStateAttribute.OPERATION_MODE] == STATE_PERFORMANCE
    )
    execute.assert_awaited_once()

    execute.reset_mock()
    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        WATER_HEATER_SERVICE_SET_OPERATION_MODE,
        {
            ATTR_ENTITY_ID: ALTHERMA_WATER_HEATER_ENTITY_ID,
            "operation_mode": STATE_PERFORMANCE,
        },
        blocking=True,
    )

    execute.assert_not_awaited()


async def test_water_heater_selecting_heat_pump_disables_powerful_mode_when_off(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Disable a stale powerful-mode flag when turning the tank on in heat-pump mode."""
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    coordinator = config_entry.runtime_data
    execute = _execute_typed_command(config_entry, mock_onecta_client)
    coordinator.async_execute_command = execute
    gateway = next(iter(coordinator.data.values()))
    point = next(
        point
        for point in gateway.device.management_points
        if point.management_point_type == "domesticHotWaterTank"
    )
    assert point.domestic_hot_water is not None
    assert point.domestic_hot_water.powerful_mode is not None
    point.on_off_mode.value = "off"
    point.domestic_hot_water.powerful_mode.value = "on"
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        WATER_HEATER_SERVICE_SET_OPERATION_MODE,
        {
            ATTR_ENTITY_ID: ALTHERMA_WATER_HEATER_ENTITY_ID,
            "operation_mode": STATE_HEAT_PUMP,
        },
        blocking=True,
    )

    assert mock_onecta_client.patch_characteristic.await_args_list == [
        call(gateway.id, point.embedded_id, "onOffMode", "on", path=None),
        call(gateway.id, point.embedded_id, "powerfulMode", "off", path=None),
    ]
    assert point.on_off_mode.value == "on"
    assert point.domestic_hot_water.powerful_mode.value == "off"
