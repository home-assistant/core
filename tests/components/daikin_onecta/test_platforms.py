"""Tests for Daikin Onecta platforms other than climate."""

from collections.abc import Awaitable, Callable
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from daikin_onecta.client import OnectaClient
import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.daikin_onecta.binary_sensor import DaikinBinarySensor
from homeassistant.components.daikin_onecta.device import DaikinOnectaDevice
from homeassistant.components.daikin_onecta.fan import DaikinAirPurifier
from homeassistant.components.daikin_onecta.select import DaikinScheduleSelect
from homeassistant.components.daikin_onecta.sensor import (
    DaikinEnergySensor,
    DaikinValueSensor,
    add_energy_sensors,
)
from homeassistant.components.daikin_onecta.switch import DaikinSwitch
from homeassistant.components.daikin_onecta.update import DaikinFirmwareUpdateEntity
from homeassistant.components.daikin_onecta.water_heater import DaikinWaterTank
from homeassistant.components.fan import (
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_TURN_OFF as FAN_SERVICE_TURN_OFF,
    SERVICE_TURN_ON as FAN_SERVICE_TURN_ON,
    FanEntityFeature,
)
from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF as SWITCH_SERVICE_TURN_OFF,
    SERVICE_TURN_ON as SWITCH_SERVICE_TURN_ON,
)
from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN, SERVICE_INSTALL
from homeassistant.components.water_heater import (
    DOMAIN as WATER_HEATER_DOMAIN,
    SERVICE_SET_TEMPERATURE as WATER_HEATER_SERVICE_SET_TEMPERATURE,
    SERVICE_TURN_OFF as WATER_HEATER_SERVICE_TURN_OFF,
    SERVICE_TURN_ON as WATER_HEATER_SERVICE_TURN_ON,
    STATE_HEAT_PUMP,
    STATE_OFF,
    STATE_PERFORMANCE,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .test_climate_snapshots import _async_setup_fixture, _load_gateway_devices

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "entity_class",
    [
        DaikinAirPurifier,
        DaikinBinarySensor,
        DaikinEnergySensor,
        DaikinFirmwareUpdateEntity,
        DaikinScheduleSelect,
        DaikinValueSensor,
        DaikinSwitch,
        DaikinWaterTank,
    ],
)
@pytest.mark.parametrize(
    ("last_update_success", "device_available", "management_point_exists", "expected"),
    [
        (True, True, True, True),
        (False, True, True, False),
        (True, False, True, False),
        (True, True, False, False),
    ],
)
def test_platform_availability_requires_coordinator_and_device(
    entity_class: type,
    last_update_success: bool,
    device_available: bool,
    management_point_exists: bool,
    expected: bool,
) -> None:
    """Entities require a successful update and their management point."""
    entity = object.__new__(entity_class)
    entity.coordinator = type(
        "Coordinator", (), {"last_update_success": last_update_success}
    )()
    entity._embedded_id = "point"
    entity._device = type(
        "Device",
        (),
        {
            "available": device_available,
            "management_point": lambda _, __: (
                object() if management_point_exists else None
            ),
        },
    )()

    assert entity.available is expected


def test_unsupported_energy_aggregate_is_skipped() -> None:
    """Do not prevent platform setup for an unrepresented energy aggregate."""
    sensors = []

    add_energy_sensors(
        MagicMock(),
        MagicMock(),
        SimpleNamespace(
            embedded_id="outdoorUnit",
            management_point_type="outdoorUnit",
            energy_aggregates=[
                SimpleNamespace(
                    source="thermal",
                    operation_mode="heating",
                    period="day",
                    data_type="output",
                )
            ],
        ),
        sensors,
    )

    assert sensors == []


def _execute_typed_command(config_entry: MockConfigEntry) -> AsyncMock:
    """Execute a typed command callback without making a cloud request."""
    api = config_entry.runtime_data.api
    api.client.patch_characteristic = AsyncMock()
    api.client.put_management_point = AsyncMock()
    api.client.install_firmware = AsyncMock()

    async def execute(command) -> bool:
        await command(api.client)
        return True

    return AsyncMock(side_effect=execute)


async def test_refresh_button_requests_coordinator_refresh(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """The refresh button requests one coordinator refresh."""
    await _async_setup_fixture(hass, config_entry, "dry")
    coordinator = config_entry.runtime_data
    coordinator.async_refresh = AsyncMock()

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.lounge_refresh"},
        blocking=True,
    )

    coordinator.async_refresh.assert_awaited_once()


async def test_refresh_button_reports_failed_refresh(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """A failed cloud refresh is reported to the service caller."""
    await _async_setup_fixture(hass, config_entry, "dry")
    coordinator = config_entry.runtime_data

    async def fail_refresh() -> None:
        coordinator.last_update_success = False

    coordinator.async_refresh = AsyncMock(side_effect=fail_refresh)

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.lounge_refresh"},
            blocking=True,
        )

    assert err.value.translation_domain == "daikin_onecta"
    assert err.value.translation_key == "refresh_failed"
    assert err.value.translation_placeholders == {"device": "Lounge"}
    coordinator.async_refresh.assert_awaited_once()


async def test_switch_service_updates_cached_state(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """A successful switch command updates the state without a cloud refresh."""
    await _async_setup_fixture(hass, config_entry, "altherma")
    config_entry.runtime_data.api.async_execute_command = _execute_typed_command(
        config_entry
    )

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SWITCH_SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.johnny_maaike_econo_mode"},
        blocking=True,
    )

    state = hass.states.get("switch.johnny_maaike_econo_mode")
    assert state is not None
    assert state.state == "off"

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SWITCH_SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: state.entity_id},
        blocking=True,
    )
    assert hass.states.get(state.entity_id).state == "on"


async def test_switch_updates_sibling_climate_preset(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """A shared preset change immediately reaches the sibling climate entity."""
    await _async_setup_fixture(hass, config_entry, "altherma")
    config_entry.runtime_data.api.async_execute_command = _execute_typed_command(
        config_entry
    )
    entity_id = "climate.johnny_maaike_room_temperature"
    assert hass.states.get(entity_id).attributes["preset_mode"] == "eco"

    for service, expected in (
        (SWITCH_SERVICE_TURN_OFF, "none"),
        (SWITCH_SERVICE_TURN_ON, "eco"),
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            service,
            {ATTR_ENTITY_ID: "switch.johnny_maaike_econo_mode"},
            blocking=True,
        )
        assert hass.states.get(entity_id).attributes["preset_mode"] == expected


@pytest.mark.parametrize(
    ("fixture", "domain", "service", "entity_id", "data", "attribute", "expected"),
    [
        (
            "altherma_boost",
            WATER_HEATER_DOMAIN,
            WATER_HEATER_SERVICE_SET_TEMPERATURE,
            "water_heater.altherma",
            {ATTR_TEMPERATURE: 50},
            "temperature",
            50,
        ),
        (
            "mc80z",
            FAN_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            "fan.air_purifier",
            {"preset_mode": "autoFan"},
            "preset_mode",
            "autoFan",
        ),
        (
            "mc80z",
            FAN_DOMAIN,
            SERVICE_SET_PERCENTAGE,
            "fan.air_purifier",
            {"percentage": 100},
            "percentage",
            100,
        ),
    ],
)
async def test_command_cache_survives_model_replacement(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fixture: str,
    domain: str,
    service: str,
    entity_id: str,
    data: dict[str, str | int],
    attribute: str,
    expected: str | int,
) -> None:
    """Update the current model if polling replaces it while a command waits."""
    await _async_setup_fixture(hass, config_entry, fixture)
    coordinator = config_entry.runtime_data
    execute = _execute_typed_command(config_entry)
    coordinator.api.async_execute_command = execute
    if service == SERVICE_SET_PERCENTAGE:
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: entity_id, "preset_mode": "manualFan"},
            blocking=True,
        )

    async def replace_model(command: Callable[[OnectaClient], Awaitable[None]]) -> bool:
        for device in coordinator.data.values():
            device.set_device_data(deepcopy(device.device))
        return await execute(command)

    coordinator.api.async_execute_command = AsyncMock(side_effect=replace_model)
    await hass.services.async_call(
        domain,
        service,
        {ATTR_ENTITY_ID: entity_id, **data},
        blocking=True,
    )

    assert hass.states.get(entity_id).attributes[attribute] == expected


async def test_air_purifier_speed_updates_captured_mode_after_model_replacement(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """A changed cloud mode does not redirect a pending speed command or its cache."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    coordinator = config_entry.runtime_data
    execute = _execute_typed_command(config_entry)
    coordinator.api.async_execute_command = execute
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: "fan.air_purifier", "preset_mode": "manualFan"},
        blocking=True,
    )
    device = next(
        device
        for device in coordinator.data.values()
        if device.device.management_points_by_type("climateControl")[0].air_purification
        is not None
    )
    embedded_id = device.device.management_points_by_type("climateControl")[
        0
    ].embedded_id
    coordinator.api.client.patch_characteristic.reset_mock()

    async def replace_model(command: Callable[[OnectaClient], Awaitable[None]]) -> bool:
        device.set_device_data(deepcopy(device.device))
        device.management_point(embedded_id).air_purification.mode.value = "autoFan"
        return await execute(command)

    coordinator.api.async_execute_command = AsyncMock(side_effect=replace_model)
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: "fan.air_purifier", "percentage": 100},
        blocking=True,
    )

    coordinator.api.client.patch_characteristic.assert_awaited_once_with(
        device.id,
        embedded_id,
        "fanControl",
        4,
        path="/airPurificationModes/manualFan/fanSpeed/modes/fixed",
    )
    purification = device.management_point(embedded_id).air_purification
    assert purification.mode.value == "autoFan"
    assert purification.fan_operation("manualFan").fan_speed.modes["fixed"].value == 4


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
    ("operation", "temperature_settable", "translation_key"),
    [
        (STATE_OFF, True, "water_heater_off"),
        (STATE_HEAT_PUMP, False, "water_heater_temperature_not_settable"),
        (STATE_HEAT_PUMP, None, "water_heater_temperature_not_settable"),
    ],
)
async def test_water_heater_rejects_unavailable_temperature_control(
    operation: str,
    temperature_settable: bool | None,
    translation_key: str,
) -> None:
    """Reject temperature writes when the tank cannot accept them."""
    if temperature_settable is None:
        entity = object.__new__(DaikinWaterTank)
        entity._device = MagicMock(
            name="Tank",
            management_point=MagicMock(
                return_value=SimpleNamespace(
                    domestic_hot_water=SimpleNamespace(temperature=None)
                )
            ),
        )
        entity._embedded_id = "tank"
    else:
        device = DaikinOnectaDevice(_load_gateway_devices("altherma_boost")[0])
        point = device.device.management_points_by_type("domesticHotWaterTank")[0]
        assert point.domestic_hot_water is not None
        assert point.domestic_hot_water.temperature is not None
        point.domestic_hot_water.temperature.settable = temperature_settable
        entity = DaikinWaterTank(device, MagicMock(), point.embedded_id)
    entity._attr_current_operation = operation
    entity._async_execute_hot_water_command = AsyncMock()

    with pytest.raises(ServiceValidationError) as err:
        await entity.async_set_tank_temperature(50)

    assert err.value.translation_key == translation_key
    entity._async_execute_hot_water_command.assert_not_awaited()


async def test_schedule_select_updates_cached_selection(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Selecting a schedule updates the entity state without a cloud refresh."""
    await _async_setup_fixture(hass, config_entry, "schedule")
    config_entry.runtime_data.api.async_execute_command = _execute_typed_command(
        config_entry
    )

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.master_schedule", "option": "1"},
        blocking=True,
    )

    state = hass.states.get("select.master_schedule")
    assert state is not None
    assert state.state == "1"


async def test_schedule_select_ignores_current_option(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Do not spend a cloud request when the selected schedule is unchanged."""
    await _async_setup_fixture(hass, config_entry, "schedule")
    execute_command = _execute_typed_command(config_entry)
    config_entry.runtime_data.api.async_execute_command = execute_command
    state = hass.states.get("select.master_schedule")
    assert state is not None

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: state.entity_id, "option": state.state},
        blocking=True,
    )

    execute_command.assert_not_awaited()


async def test_schedule_select_rejects_missing_selection() -> None:
    """Reject a selection when Daikin no longer provides schedule data."""
    entity = object.__new__(DaikinScheduleSelect)
    object.__setattr__(entity, "_device", MagicMock(name="Device"))
    entity.selection = MagicMock(return_value=None)

    with pytest.raises(ServiceValidationError) as err:
        await entity.async_select_option("Schedule")

    assert err.value.translation_key == "schedule_selection_unavailable"


async def test_schedule_select_rejects_unadvertised_option() -> None:
    """Reject a schedule option that is not advertised by the device."""
    entity = object.__new__(DaikinScheduleSelect)
    object.__setattr__(entity, "_device", MagicMock(name="Device"))
    entity.selection = MagicMock(return_value=MagicMock())
    entity.get_options = MagicMock(return_value=[])

    with pytest.raises(ServiceValidationError) as err:
        await entity.async_select_option("Schedule")

    assert err.value.translation_key == "schedule_option_unavailable"


@pytest.mark.parametrize(
    ("current_operation", "supported_features", "method", "translation_key"),
    [
        (
            STATE_OFF,
            WaterHeaterEntityFeature(0),
            "async_turn_on",
            "water_heater_on_off_unavailable",
        ),
        (
            STATE_HEAT_PUMP,
            WaterHeaterEntityFeature(0),
            "async_turn_off",
            "water_heater_on_off_unavailable",
        ),
    ],
)
async def test_water_heater_rejects_unavailable_power_control(
    current_operation: str,
    supported_features: WaterHeaterEntityFeature,
    method: str,
    translation_key: str,
) -> None:
    """Reject turning a water heater on or off without a writable power control."""
    entity = object.__new__(DaikinWaterTank)
    object.__setattr__(entity, "_device", MagicMock(name="Device"))
    object.__setattr__(entity, "_attr_current_operation", current_operation)
    object.__setattr__(entity, "_attr_supported_features", supported_features)

    with pytest.raises(ServiceValidationError) as err:
        await getattr(entity, method)()

    assert err.value.translation_key == translation_key


async def test_water_heater_rejects_unadvertised_operation_mode() -> None:
    """Reject an operation mode that the heater does not advertise."""
    entity = object.__new__(DaikinWaterTank)
    object.__setattr__(entity, "_device", MagicMock(name="Device"))
    entity.get_operation_list = MagicMock(return_value=[STATE_OFF])

    with pytest.raises(ServiceValidationError) as err:
        await entity.async_set_operation_mode(STATE_HEAT_PUMP)

    assert err.value.translation_key == "water_heater_operation_mode_unavailable"


@pytest.mark.parametrize(
    ("method", "args", "translation_key"),
    [
        ("async_turn_on", (), "air_purifier_power_unavailable"),
        ("async_turn_off", (), "air_purifier_power_unavailable"),
        ("async_set_preset_mode", ("autoFan",), "air_purifier_mode_unavailable"),
        ("async_set_percentage", (100,), "air_purifier_speed_unavailable"),
    ],
)
async def test_air_purifier_rejects_unavailable_controls(
    method: str, args: tuple[object, ...], translation_key: str
) -> None:
    """Reject purifier controls that are not provided by the device."""
    entity = object.__new__(DaikinAirPurifier)
    object.__setattr__(entity, "_device", MagicMock(name="Device"))
    entity._air_purification = MagicMock(return_value=None)

    with pytest.raises(ServiceValidationError) as err:
        await getattr(entity, method)(*args)

    assert err.value.translation_key == translation_key


async def test_water_heater_turn_off_updates_cached_state(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """A successful water-heater command updates the cached operation mode."""
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    config_entry.runtime_data.api.async_execute_command = _execute_typed_command(
        config_entry
    )
    listener = MagicMock()
    remove_listener = config_entry.runtime_data.async_add_listener(listener)

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        WATER_HEATER_SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "water_heater.altherma"},
        blocking=True,
    )

    state = hass.states.get("water_heater.altherma")
    assert state is not None
    assert state.attributes["operation_mode"] == "off"

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        WATER_HEATER_SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: state.entity_id},
        blocking=True,
    )
    state = hass.states.get(state.entity_id)
    assert state is not None
    assert state.attributes["operation_mode"] == STATE_PERFORMANCE
    assert listener.call_count == 2
    remove_listener()


async def test_water_heater_temperature_updates_typed_cache(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """A successful temperature write updates the shared typed model."""
    await _async_setup_fixture(hass, config_entry, "altherma_boost")
    config_entry.runtime_data.api.async_execute_command = _execute_typed_command(
        config_entry
    )
    listener = MagicMock()
    remove_listener = config_entry.runtime_data.async_add_listener(listener)

    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        WATER_HEATER_SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "water_heater.altherma", ATTR_TEMPERATURE: 50},
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


async def test_water_heater_publishes_successful_partial_operation_write() -> None:
    """Keep the successful power write visible if powerful mode later fails."""
    entity = object.__new__(DaikinWaterTank)
    power = SimpleNamespace(value="off", settable=True)
    powerful_mode = SimpleNamespace(value="off", settable=True)
    hot_water = SimpleNamespace(
        power=power,
        powerful_mode=powerful_mode,
        temperature=None,
        current_temperature=None,
    )
    entity._device = MagicMock(
        name="Tank",
        management_point=MagicMock(
            return_value=SimpleNamespace(
                domestic_hot_water=hot_water,
                on_off_mode=power,
            )
        ),
    )
    entity._embedded_id = "tank"
    entity._attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    entity._attr_current_operation = "off"
    entity._attr_operation_list = ["off", STATE_HEAT_PUMP, STATE_PERFORMANCE]
    entity._async_execute_hot_water_command = AsyncMock(
        side_effect=[None, HomeAssistantError]
    )
    entity.coordinator = MagicMock()

    with pytest.raises(HomeAssistantError):
        await entity.async_set_operation_mode(STATE_PERFORMANCE)

    assert power.value == "on"
    assert entity.current_operation == STATE_HEAT_PUMP
    entity.coordinator.async_update_listeners.assert_called_once()


async def test_firmware_install_executes_command(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """The update service executes the typed firmware-install command."""
    await _async_setup_fixture(hass, config_entry, "dx4_firmwareavailable")
    config_entry.runtime_data.api.async_execute_command = _execute_typed_command(
        config_entry
    )

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.johnny_maaike_firmware_update"},
        blocking=True,
    )

    config_entry.runtime_data.api.async_execute_command.assert_awaited_once()
    state = hass.states.get("update.johnny_maaike_firmware_update")
    assert state is not None
    assert state.attributes["in_progress"] is False


@pytest.mark.parametrize("update_supported", [False, True])
async def test_firmware_install_rejects_unavailable_firmware(
    update_supported: bool,
) -> None:
    """Do not issue a cloud command without a usable firmware offer."""
    entity = object.__new__(DaikinFirmwareUpdateEntity)
    entity._device = MagicMock(name="Device")
    entity._is_update_supported = update_supported
    entity._firmware_id = None
    entity._async_execute_command = AsyncMock()

    with pytest.raises(ServiceValidationError) as err:
        await entity.async_install(None, False)

    assert err.value.translation_key == "firmware_install_unavailable"
    entity._async_execute_command.assert_not_awaited()


async def test_air_purifier_preset_updates_cached_state(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """A successful purifier command updates its native preset state."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    config_entry.runtime_data.api.async_execute_command = _execute_typed_command(
        config_entry
    )

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: "fan.air_purifier", "preset_mode": "autoFan"},
        blocking=True,
    )

    state = hass.states.get("fan.air_purifier")
    assert state is not None
    assert state.attributes["preset_mode"] == "autoFan"


async def test_air_purifier_percentage_switches_to_manual_and_updates_cache(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Setting speed selects the writable manual mode and updates its cache."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    config_entry.runtime_data.api.async_execute_command = _execute_typed_command(
        config_entry
    )

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: "fan.air_purifier", "preset_mode": "manualFan"},
        blocking=True,
    )
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: "fan.air_purifier", "percentage": 100},
        blocking=True,
    )

    state = hass.states.get("fan.air_purifier")
    assert state is not None
    assert state.attributes["preset_mode"] == "manualFan"
    assert state.attributes["percentage"] == 100


async def test_air_purifier_turn_off_then_on_updates_cached_state(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Power commands immediately publish their successful local state."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    config_entry.runtime_data.api.async_execute_command = _execute_typed_command(
        config_entry
    )

    await hass.services.async_call(
        FAN_DOMAIN,
        FAN_SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "fan.air_purifier"},
        blocking=True,
    )
    state = hass.states.get("fan.air_purifier")
    assert state is not None
    assert state.state == "off"

    await hass.services.async_call(
        FAN_DOMAIN,
        FAN_SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "fan.air_purifier"},
        blocking=True,
    )
    state = hass.states.get("fan.air_purifier")
    assert state is not None
    assert state.state == "on"


async def test_air_purifier_ignores_unchanged_preset(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Do not spend a cloud request when the selected purifier mode is unchanged."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    execute_command = _execute_typed_command(config_entry)
    config_entry.runtime_data.api.async_execute_command = execute_command

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: "fan.air_purifier", "preset_mode": "econo"},
        blocking=True,
    )

    execute_command.assert_not_awaited()


async def test_air_purifier_does_not_expose_read_only_preset_modes() -> None:
    """Do not expose a preset service for a read-only Daikin mode."""
    entity = object.__new__(DaikinAirPurifier)
    purification = SimpleNamespace(
        power=SimpleNamespace(value="on"),
        mode=SimpleNamespace(value="autoFan", settable=False),
        modes=["autoFan", "manualFan"],
        fan_operation=MagicMock(return_value=None),
    )
    entity._air_purification = MagicMock(return_value=purification)
    entity._device = SimpleNamespace(name="Purifier")

    entity._update_state()

    assert entity.supported_features == (
        FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
    )
    assert entity.preset_modes == []
    with pytest.raises(HomeAssistantError):
        await entity.async_set_preset_mode("manualFan")


def test_unknown_binary_sensor_uses_generic_description() -> None:
    """A new boolean cloud characteristic must not prevent platform setup."""
    device = MagicMock(id="device", name="Device")
    device.management_point.return_value = SimpleNamespace(
        scalar_characteristic=MagicMock(return_value=SimpleNamespace(value=True))
    )

    entity = DaikinBinarySensor(device, MagicMock(), "point", "futureBoolean")

    assert entity.entity_description.key == "futureBoolean"
    assert entity.is_on is True
