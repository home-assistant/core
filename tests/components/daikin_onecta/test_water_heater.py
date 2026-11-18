"""Tests for Daikin Onecta water heater entities."""

from unittest.mock import AsyncMock, MagicMock, call

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.daikin_onecta.device import DaikinOnectaDevice
from homeassistant.components.daikin_onecta.water_heater import DaikinWaterTank
from homeassistant.components.water_heater import (
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
from homeassistant.util.unit_system import (
    METRIC_SYSTEM,
    US_CUSTOMARY_SYSTEM,
    UnitSystem,
)

from .platform_helpers import _execute_typed_command
from .test_climate_snapshots import _async_setup_fixture, _load_gateway_devices


@pytest.mark.parametrize("power_settable", [False, True])
def test_water_heater_features_follow_power_capability(power_settable: bool) -> None:
    """Only advertise power and operation controls for a writable characteristic."""
    device = DaikinOnectaDevice(_load_gateway_devices("holidaymode")[0])
    point = device.device.management_points_by_type("domesticHotWaterFlowThrough")[0]
    point.on_off_mode.settable = power_settable
    entity = DaikinWaterTank(device, MagicMock(), point.embedded_id)

    expected = (
        WaterHeaterEntityFeature.ON_OFF | WaterHeaterEntityFeature.OPERATION_MODE
        if power_settable
        else WaterHeaterEntityFeature(0)
    )
    assert entity.supported_features == expected
    assert entity.operation_list == (["off", STATE_HEAT_PUMP] if power_settable else [])


@pytest.mark.parametrize(
    "method", ["async_turn_on", "async_turn_off", "async_set_operation_mode"]
)
async def test_water_heater_rejects_read_only_power(method: str) -> None:
    """Read-only water-heater actions fail without spending a cloud request."""
    device = DaikinOnectaDevice(_load_gateway_devices("holidaymode")[0])
    point = device.device.management_points_by_type("domesticHotWaterFlowThrough")[0]
    point.on_off_mode.value = "off" if method == "async_turn_on" else "on"
    entity = DaikinWaterTank(device, MagicMock(), point.embedded_id)
    entity._async_execute_hot_water_command = AsyncMock()

    with pytest.raises(HomeAssistantError):
        await getattr(entity, method)(
            *(["off"] if method == "async_set_operation_mode" else [])
        )

    entity._async_execute_hot_water_command.assert_not_awaited()


@pytest.mark.parametrize("power", ["on", "off"])
def test_water_heater_read_only_power_keeps_writable_boost(power: str) -> None:
    """Allow writable boost while powered on without advertising power control."""
    device = DaikinOnectaDevice(_load_gateway_devices("altherma_boost")[0])
    point = device.device.management_points_by_type("domesticHotWaterTank")[0]
    point.on_off_mode.settable = False
    point.on_off_mode.value = power
    entity = DaikinWaterTank(device, MagicMock(), point.embedded_id)

    assert not entity.supported_features & WaterHeaterEntityFeature.ON_OFF
    assert bool(
        entity.supported_features & WaterHeaterEntityFeature.OPERATION_MODE
    ) == (power == "on")
    assert entity.operation_list == (
        [STATE_HEAT_PUMP, STATE_PERFORMANCE] if power == "on" else []
    )


def test_water_heater_handles_missing_temperature_values() -> None:
    """Use HA defaults when Daikin omits temperature bounds and target."""
    device = DaikinOnectaDevice(_load_gateway_devices("altherma_boost")[0])
    point = device.device.management_points_by_type("domesticHotWaterTank")[0]
    assert point.domestic_hot_water is not None
    assert point.domestic_hot_water.temperature is not None
    point.domestic_hot_water.temperature.value = None
    point.domestic_hot_water.temperature.min_value = None
    point.domestic_hot_water.temperature.max_value = None

    entity = DaikinWaterTank(device, MagicMock(), point.embedded_id)

    assert entity.target_temperature is None
    assert entity.min_temp == super(DaikinWaterTank, entity).min_temp
    assert entity.max_temp == super(DaikinWaterTank, entity).max_temp


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

    entity = DaikinWaterTank(device, MagicMock(), point.embedded_id)

    assert entity.native_temperature_unit == expected_unit


def test_water_heater_uses_standard_target_temperature_step() -> None:
    """Expose the Daikin setpoint increment through the standard capability."""
    device = DaikinOnectaDevice(_load_gateway_devices("altherma_boost")[0])
    point = device.device.management_points_by_type("domesticHotWaterTank")[0]
    assert point.domestic_hot_water is not None
    assert point.domestic_hot_water.temperature is not None

    entity = DaikinWaterTank(device, MagicMock(), point.embedded_id)

    assert entity.target_temperature_step == float(
        point.domestic_hot_water.temperature.step_value
    )
    assert entity.extra_state_attributes is None


@pytest.mark.parametrize(
    ("operation", "temperature_settable"),
    [(STATE_OFF, True), (STATE_HEAT_PUMP, False), (STATE_HEAT_PUMP, None)],
)
async def test_water_heater_rejects_unavailable_temperature_control(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    operation: str,
    temperature_settable: bool | None,
) -> None:
    """Reject a HA temperature request when its device control is unavailable."""
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    coordinator = config_entry.runtime_data
    execute = _execute_typed_command(config_entry)
    coordinator.async_execute_command = execute
    gateway = next(iter(coordinator.data.values()))
    point = gateway.device.management_points_by_type("domesticHotWaterTank")[0]
    point.on_off_mode.value = "off" if operation == STATE_OFF else "on"
    if temperature_settable is False:
        assert point.domestic_hot_water is not None
        assert point.domestic_hot_water.temperature is not None
        point.domestic_hot_water.temperature.settable = False
    elif temperature_settable is None:
        point.temperature_control.value.operation_modes["heating"].setpoints.pop(
            "domesticHotWaterTemperature"
        )
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    expected_translation_key = (
        "water_heater_off" if operation == STATE_OFF else "service_not_supported"
    )
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

    assert err.value.translation_key == expected_translation_key
    execute.assert_not_awaited()


@pytest.mark.parametrize(
    ("current_operation", "method"),
    [
        (STATE_OFF, "async_turn_on"),
        (STATE_HEAT_PUMP, "async_turn_off"),
    ],
)
async def test_water_heater_rejects_unavailable_power_control(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    current_operation: str,
    method: str,
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
    point.on_off_mode.value = "off" if current_operation == STATE_OFF else "on"
    point.on_off_mode.settable = False
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    state = hass.states.async_all(WATER_HEATER_DOMAIN)[0]
    assert state is not None
    service = (
        WATER_HEATER_SERVICE_TURN_ON
        if method == "async_turn_on"
        else WATER_HEATER_SERVICE_TURN_OFF
    )

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
        (METRIC_SYSTEM, 48.4, 1, 48),
        (METRIC_SYSTEM, 48.6, 1, 49),
        (US_CUSTOMARY_SYSTEM, 120, 1, 49),
        (METRIC_SYSTEM, 48.6, 0.5, 48.5),
        (METRIC_SYSTEM, 49.2, 2, 50),
        (METRIC_SYSTEM, 45.3, 0.1, 45.3),
        (METRIC_SYSTEM, 44.5, None, 45),
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
    if expected_temperature == 48:
        coordinator.client.patch_characteristic.assert_not_awaited()
    else:
        coordinator.client.patch_characteristic.assert_awaited_once_with(
            gateway.id,
            point.embedded_id,
            "temperatureControl",
            expected_temperature,
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
    ("method", "args", "power_value"),
    [
        ("async_turn_on", (), None),
        ("async_turn_off", (), None),
        ("async_set_operation_mode", (STATE_HEAT_PUMP,), None),
        ("async_set_tank_temperature", (50,), None),
        ("async_set_tank_temperature", (50,), "unknown"),
    ],
)
async def test_water_heater_rejects_unknown_power_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    method: str,
    args: tuple[object, ...],
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

    if method == "async_turn_on":
        service = WATER_HEATER_SERVICE_TURN_ON
        service_data = {}
    elif method == "async_turn_off":
        service = WATER_HEATER_SERVICE_TURN_OFF
        service_data = {}
    elif method == "async_set_operation_mode":
        service = WATER_HEATER_SERVICE_SET_OPERATION_MODE
        service_data = {"operation_mode": args[0]}
    else:
        service = WATER_HEATER_SERVICE_SET_TEMPERATURE
        service_data = {WaterHeaterServiceArgument.TEMPERATURE: args[0]}

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
    config_entry.runtime_data.async_execute_command = _execute_typed_command(
        config_entry
    )

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
