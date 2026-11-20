"""Tests for Daikin Onecta water heater entities."""

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, MagicMock, call

from daikin_onecta.models import ManagementPoint
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.daikin_onecta.device import DaikinOnectaDevice
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
from homeassistant.util.unit_conversion import TemperatureConverter
from homeassistant.util.unit_system import (
    METRIC_SYSTEM,
    US_CUSTOMARY_SYSTEM,
    UnitSystem,
)

from .platform_helpers import _execute_typed_command, _mock_coordinator
from .test_climate_snapshots import _async_setup_fixture, _load_gateway_devices


@pytest.mark.parametrize(
    ("power_settable", "expected_features", "expected_operation_list"),
    [
        pytest.param(False, WaterHeaterEntityFeature(0), [], id="read-only"),
        pytest.param(
            True,
            WaterHeaterEntityFeature.ON_OFF | WaterHeaterEntityFeature.OPERATION_MODE,
            ["off", STATE_HEAT_PUMP],
            id="writable",
        ),
    ],
)
def test_water_heater_features_follow_power_capability(
    power_settable: bool,
    expected_features: WaterHeaterEntityFeature,
    expected_operation_list: list[str],
) -> None:
    """Only advertise power and operation controls for a writable characteristic."""
    device = DaikinOnectaDevice(_load_gateway_devices("holidaymode")[0])
    point = device.device.management_points_by_type("domesticHotWaterFlowThrough")[0]
    point.on_off_mode.settable = power_settable
    entity = DaikinWaterTank(device, _mock_coordinator(device), point.embedded_id)

    assert entity.supported_features == expected_features
    assert entity.operation_list == expected_operation_list


@pytest.mark.parametrize(
    ("method", "power_value", "args"),
    [
        pytest.param(DaikinWaterTank.async_turn_on, "off", (), id="turn-on"),
        pytest.param(DaikinWaterTank.async_turn_off, "on", (), id="turn-off"),
        pytest.param(
            DaikinWaterTank.async_set_operation_mode,
            "on",
            ("off",),
            id="operation-mode",
        ),
    ],
)
async def test_water_heater_rejects_read_only_power(
    method: Callable[..., Awaitable[None]], power_value: str, args: tuple[str, ...]
) -> None:
    """Read-only water-heater actions fail without spending a cloud request."""
    device = DaikinOnectaDevice(_load_gateway_devices("holidaymode")[0])
    point = device.device.management_points_by_type("domesticHotWaterFlowThrough")[0]
    point.on_off_mode.value = power_value
    entity = DaikinWaterTank(device, _mock_coordinator(device), point.embedded_id)
    entity._async_execute_hot_water_command = AsyncMock()

    with pytest.raises(HomeAssistantError):
        await method(entity, *args)

    entity._async_execute_hot_water_command.assert_not_awaited()


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
        pytest.param("off", WaterHeaterEntityFeature.TARGET_TEMPERATURE, [], id="off"),
    ],
)
def test_water_heater_read_only_power_keeps_writable_boost(
    power: str,
    expected_features: WaterHeaterEntityFeature,
    expected_operation_list: list[str],
) -> None:
    """Allow writable boost while powered on without advertising power control."""
    device = DaikinOnectaDevice(_load_gateway_devices("altherma_boost")[0])
    point = device.device.management_points_by_type("domesticHotWaterTank")[0]
    point.on_off_mode.settable = False
    point.on_off_mode.value = power
    entity = DaikinWaterTank(device, _mock_coordinator(device), point.embedded_id)

    assert entity.supported_features == expected_features
    assert entity.operation_list == expected_operation_list


def test_water_heater_handles_missing_temperature_values() -> None:
    """Restore HA defaults when Daikin stops reporting temperature bounds."""
    device = DaikinOnectaDevice(_load_gateway_devices("altherma_boost")[0])
    point = device.device.management_points_by_type("domesticHotWaterTank")[0]
    assert point.domestic_hot_water is not None
    assert point.domestic_hot_water.temperature is not None
    point.domestic_hot_water.temperature.min_value = 45
    point.domestic_hot_water.temperature.max_value = 60
    entity = DaikinWaterTank(device, _mock_coordinator(device), point.embedded_id)
    assert entity.min_temp == 45
    assert entity.max_temp == 60

    point.domestic_hot_water.temperature.value = None
    point.domestic_hot_water.temperature.min_value = None
    point.domestic_hot_water.temperature.max_value = None
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
def test_water_heater_uses_daikin_temperature_unit(
    setpoint_unit: str | None,
    sensory_unit: str | None,
    expected_unit: UnitOfTemperature,
) -> None:
    """Use the reported setpoint or tank-sensor unit, defaulting to Celsius."""
    device = DaikinOnectaDevice(_load_gateway_devices("altherma_boost")[0])
    point = device.device.management_points_by_type("domesticHotWaterTank")[0]
    setpoint = point.domestic_hot_water.temperature
    tank_temperature = point.sensory_characteristic("tankTemperature")
    assert setpoint is not None
    assert tank_temperature is not None
    setpoint.unit = setpoint_unit
    tank_temperature.unit = sensory_unit

    entity = DaikinWaterTank(device, _mock_coordinator(device), point.embedded_id)

    assert entity.native_temperature_unit == expected_unit


@pytest.mark.parametrize(
    ("step_value", "expected_step"),
    [(None, 1.0), (0.5, 0.5)],
)
def test_water_heater_uses_standard_target_temperature_step(
    step_value: float | None, expected_step: float
) -> None:
    """Expose the Daikin increment or the whole-degree fallback."""
    device = DaikinOnectaDevice(_load_gateway_devices("altherma_boost")[0])
    point = device.device.management_points_by_type("domesticHotWaterTank")[0]
    assert point.domestic_hot_water is not None
    assert point.domestic_hot_water.temperature is not None
    point.domestic_hot_water.temperature.step_value = step_value

    entity = DaikinWaterTank(device, _mock_coordinator(device), point.embedded_id)

    assert entity.target_temperature_step == expected_step
    assert entity.extra_state_attributes is None


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
) -> None:
    """Reject a HA temperature request when its device control is unavailable."""
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    coordinator = config_entry.runtime_data
    execute = _execute_typed_command(config_entry)
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
                ATTR_ENTITY_ID: "water_heater.altherma_domestic_hot_water_tank",
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
) -> None:
    """Reject unsupported power actions through Home Assistant services."""
    await _async_setup_fixture(hass, config_entry, "holidaymode")
    coordinator = config_entry.runtime_data
    execute = _execute_typed_command(config_entry)
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
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Reject an operation mode through HA that Daikin does not advertise."""
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    execute = _execute_typed_command(config_entry)
    config_entry.runtime_data.async_execute_command = execute

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            WATER_HEATER_SERVICE_SET_OPERATION_MODE,
            {
                ATTR_ENTITY_ID: "water_heater.altherma_domestic_hot_water_tank",
                "operation_mode": "unsupported_mode",
            },
            blocking=True,
        )

    execute.assert_not_awaited()


async def test_water_heater_turn_off_updates_cached_state(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """A successful water-heater command updates the cached operation mode."""
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    config_entry.runtime_data.async_execute_command = _execute_typed_command(
        config_entry
    )
    listener = MagicMock()
    remove_listener = config_entry.runtime_data.async_add_listener(listener)

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        WATER_HEATER_SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "water_heater.altherma_domestic_hot_water_tank"},
        blocking=True,
    )

    state = hass.states.get("water_heater.altherma_domestic_hot_water_tank")
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
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """A successful temperature write updates the shared typed model."""
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    config_entry.runtime_data.async_execute_command = _execute_typed_command(
        config_entry
    )
    listener = MagicMock()
    remove_listener = config_entry.runtime_data.async_add_listener(listener)

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        WATER_HEATER_SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: "water_heater.altherma_domestic_hot_water_tank",
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
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Apply a non-off mode before a combined temperature write."""
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    coordinator = config_entry.runtime_data
    coordinator.async_execute_command = _execute_typed_command(config_entry)
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
            ATTR_ENTITY_ID: "water_heater.altherma_domestic_hot_water_tank",
            WaterHeaterServiceArgument.OPERATION_MODE: STATE_HEAT_PUMP,
            WaterHeaterServiceArgument.TEMPERATURE: 50,
        },
        blocking=True,
    )

    assert coordinator.client.patch_characteristic.await_args_list == [
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
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Write the target temperature before turning the tank off."""
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    coordinator = config_entry.runtime_data
    coordinator.async_execute_command = _execute_typed_command(config_entry)
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
            ATTR_ENTITY_ID: "water_heater.altherma_domestic_hot_water_tank",
            WaterHeaterServiceArgument.OPERATION_MODE: STATE_OFF,
            WaterHeaterServiceArgument.TEMPERATURE: 50,
        },
        blocking=True,
    )

    assert coordinator.client.patch_characteristic.await_args_list == [
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
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Do not write the temperature when the heater is already off."""
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    coordinator = config_entry.runtime_data
    execute = _execute_typed_command(config_entry)
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
                ATTR_ENTITY_ID: "water_heater.altherma_domestic_hot_water_tank",
                WaterHeaterServiceArgument.OPERATION_MODE: STATE_OFF,
                WaterHeaterServiceArgument.TEMPERATURE: 50,
            },
            blocking=True,
        )

    assert err.value.translation_key == "water_heater_off"
    execute.assert_not_awaited()


async def test_water_heater_rejects_invalid_combined_mode_before_temperature_write(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Validate the requested mode before writing a combined temperature."""
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    coordinator = config_entry.runtime_data
    execute = _execute_typed_command(config_entry)
    coordinator.async_execute_command = execute

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            WATER_HEATER_SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: "water_heater.altherma_domestic_hot_water_tank",
                WaterHeaterServiceArgument.OPERATION_MODE: "unsupported_mode",
                WaterHeaterServiceArgument.TEMPERATURE: 50,
            },
            blocking=True,
        )

    execute.assert_not_awaited()


async def test_water_heater_temperature_writes_without_power_characteristic(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """A settable temperature remains usable without on/off control."""
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    coordinator = config_entry.runtime_data
    execute = _execute_typed_command(config_entry)
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
            ATTR_ENTITY_ID: "water_heater.altherma_domestic_hot_water_tank",
            WaterHeaterServiceArgument.TEMPERATURE: 50,
        },
        blocking=True,
    )

    assert point.domestic_hot_water is not None
    assert point.domestic_hot_water.temperature is not None
    assert point.domestic_hot_water.temperature.value == 50
    coordinator.client.patch_characteristic.assert_awaited_once_with(
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
) -> None:
    """Round requested temperatures to the nearest supported native step."""
    hass.config.units = unit_system
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    coordinator = config_entry.runtime_data
    execute = _execute_typed_command(config_entry)
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
            ATTR_ENTITY_ID: "water_heater.altherma_domestic_hot_water_tank",
            WaterHeaterServiceArgument.TEMPERATURE: service_temperature,
        },
        blocking=True,
    )

    assert point.domestic_hot_water.temperature.value == expected_temperature
    coordinator.client.patch_characteristic.assert_awaited_once_with(
        gateway.id,
        point.embedded_id,
        "temperatureControl",
        expected_temperature,
        path="/operationModes/heating/setpoints/domesticHotWaterTemperature",
    )


async def test_water_heater_rounded_current_temperature_does_not_write(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Skip a request when the rounded target equals the current tank target."""
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    coordinator = config_entry.runtime_data
    coordinator.async_execute_command = _execute_typed_command(config_entry)
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
            ATTR_ENTITY_ID: "water_heater.altherma_domestic_hot_water_tank",
            WaterHeaterServiceArgument.TEMPERATURE: 48.4,
        },
        blocking=True,
    )

    coordinator.client.patch_characteristic.assert_not_awaited()


async def test_water_heater_temperature_rounding_is_anchored_to_minimum(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Round relative to a nonzero, non-step-aligned tank temperature minimum."""
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    coordinator = config_entry.runtime_data
    coordinator.async_execute_command = _execute_typed_command(config_entry)
    gateway = next(iter(coordinator.data.values()))
    point = gateway.device.management_points_by_type("domesticHotWaterTank")[0]
    assert point.domestic_hot_water is not None
    setpoint = point.domestic_hot_water.temperature
    assert setpoint is not None
    setpoint.min_value = 43.3
    setpoint.max_value = 60
    setpoint.step_value = 0.5

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        WATER_HEATER_SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: "water_heater.altherma_domestic_hot_water_tank",
            WaterHeaterServiceArgument.TEMPERATURE: 44,
        },
        blocking=True,
    )

    assert setpoint.value == 43.8
    coordinator.client.patch_characteristic.assert_awaited_once_with(
        gateway.id,
        point.embedded_id,
        "temperatureControl",
        43.8,
        path="/operationModes/heating/setpoints/domesticHotWaterTemperature",
    )


async def test_water_heater_temperature_is_clamped_to_setpoint_range(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Clamp service values to Daikin's setpoint bounds before writing."""
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    coordinator = config_entry.runtime_data
    coordinator.async_execute_command = _execute_typed_command(config_entry)
    gateway = next(iter(coordinator.data.values()))
    point = gateway.device.management_points_by_type("domesticHotWaterTank")[0]
    assert point.domestic_hot_water is not None
    setpoint = point.domestic_hot_water.temperature
    assert setpoint is not None
    assert setpoint.max_value is not None
    setpoint.step_value = 0.5
    expected = float(setpoint.max_value)

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        WATER_HEATER_SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: "water_heater.altherma_domestic_hot_water_tank",
            WaterHeaterServiceArgument.TEMPERATURE: expected + 10,
        },
        blocking=True,
    )

    coordinator.client.patch_characteristic.assert_awaited_once_with(
        gateway.id,
        point.embedded_id,
        "temperatureControl",
        expected,
        path="/operationModes/heating/setpoints/domesticHotWaterTemperature",
    )


async def test_water_heater_does_not_clamp_to_ha_defaults_without_daikin_limits(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Do not clamp to Home Assistant defaults when Daikin omits tank limits."""
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    coordinator = config_entry.runtime_data
    coordinator.async_execute_command = _execute_typed_command(config_entry)
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
            ATTR_ENTITY_ID: "water_heater.altherma_domestic_hot_water_tank",
            WaterHeaterServiceArgument.TEMPERATURE: 40,
        },
        blocking=True,
    )

    assert setpoint.value == 40
    coordinator.client.patch_characteristic.assert_awaited_once_with(
        gateway.id,
        point.embedded_id,
        "temperatureControl",
        40,
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
                ATTR_ENTITY_ID: "water_heater.altherma_domestic_hot_water_tank",
                "operation_mode": STATE_PERFORMANCE,
            },
            blocking=True,
        )

    state = hass.states.get("water_heater.altherma_domestic_hot_water_tank")
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
) -> None:
    """Reject HA write services when Daikin omits the current power value."""
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    coordinator = config_entry.runtime_data
    execute = _execute_typed_command(config_entry)
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
                ATTR_ENTITY_ID: "water_heater.altherma_domestic_hot_water_tank",
                **service_data,
            },
            blocking=True,
        )

    assert err.value.translation_key == "water_heater_on_off_unavailable"
    execute.assert_not_awaited()


async def test_water_heater_set_performance_updates_state(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """A successful boost command updates the entity through HA's service API."""
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    execute = _execute_typed_command(config_entry)
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
            ATTR_ENTITY_ID: "water_heater.altherma_domestic_hot_water_tank",
            "operation_mode": STATE_PERFORMANCE,
        },
        blocking=True,
    )

    state = hass.states.get("water_heater.altherma_domestic_hot_water_tank")
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
            ATTR_ENTITY_ID: "water_heater.altherma_domestic_hot_water_tank",
            "operation_mode": STATE_PERFORMANCE,
        },
        blocking=True,
    )

    execute.assert_not_awaited()


async def test_water_heater_selecting_heat_pump_disables_powerful_mode_when_off(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Disable a stale powerful-mode flag when turning the tank on in heat-pump mode."""
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    coordinator = config_entry.runtime_data
    execute = _execute_typed_command(config_entry)
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
            ATTR_ENTITY_ID: "water_heater.altherma_domestic_hot_water_tank",
            "operation_mode": STATE_HEAT_PUMP,
        },
        blocking=True,
    )

    assert coordinator.client.patch_characteristic.await_args_list == [
        call(gateway.id, point.embedded_id, "onOffMode", "on", path=None),
        call(gateway.id, point.embedded_id, "powerfulMode", "off", path=None),
    ]
    assert point.on_off_mode.value == "on"
    assert point.domestic_hot_water.powerful_mode.value == "off"
