"""Tests for the Daikin Onecta climate platform."""

from collections.abc import Callable
from copy import deepcopy
from dataclasses import replace
from unittest.mock import call

from daikin_onecta.exceptions import OnectaConnectionError
from daikin_onecta.models import (
    Characteristic,
    FanDirection,
    FanDirectionAxis,
    GatewayDevice,
    ManagementPoint,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.climate import (
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DOMAIN as CLIMATE_DOMAIN,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_ECO,
    PRESET_NONE,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_SWING_HORIZONTAL_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    SWING_OFF,
    SWING_ON,
    ClimateEntityCapabilityAttribute,
    ClimateEntityFeature,
    ClimateEntityStateAttribute,
    ClimateServiceArgument,
    HVACMode,
)
from homeassistant.components.daikin_onecta.climate import DaikinClimate
from homeassistant.components.daikin_onecta.const import (
    FANMODE_FIXED,
    LEAVING_WATER_OFFSET,
)
from homeassistant.components.daikin_onecta.coordinator import (
    OnectaDataUpdateCoordinator,
)
from homeassistant.components.daikin_onecta.device import DaikinOnectaDevice
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    HomeAssistantError,
    OAuth2TokenRequestConnectionError,
    ServiceValidationError,
)
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity import EntityStateAttribute
from homeassistant.util.unit_system import (
    METRIC_SYSTEM,
    US_CUSTOMARY_SYSTEM,
    UnitSystem,
)

from .conftest import DOMAIN, MockOnectaClient
from .platform_helpers import (
    _async_fire_coordinator_update,
    _async_setup_fixture,
    _load_gateway_devices,
)

DRY_FIXED_DIRECTION_GATEWAY_ID = "00000000-0000-4000-8000-000000000108"


async def _async_setup_climate_service_fixture(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> tuple[str, str, ManagementPoint, OnectaDataUpdateCoordinator]:
    """Set up one climate fixture through Home Assistant's config-entry flow."""
    await _async_setup_fixture(hass, config_entry, "climate_fixedfanmode")
    coordinator = config_entry.runtime_data
    assert isinstance(coordinator, OnectaDataUpdateCoordinator)
    assert coordinator.data is not None
    gateway_id, device = next(iter(coordinator.data.items()))
    management_point = device.management_point("climateControl")
    assert management_point is not None
    entity_id = entity_registry.async_get_entity_id(
        Platform.CLIMATE,
        DOMAIN,
        f"{gateway_id}_{management_point.embedded_id}_roomTemperature",
    )
    assert entity_id is not None
    return entity_id, gateway_id, management_point, coordinator


async def test_target_temperature_step_clears_without_current_setpoint(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Restore Home Assistant temperature defaults without a current setpoint."""
    await _async_setup_fixture(hass, config_entry, "climate_floorheatingairflow")
    coordinator = config_entry.runtime_data
    entity_id = hass.states.async_entity_ids(CLIMATE_DOMAIN)[0]
    entity = hass.data[CLIMATE_DOMAIN].get_entity(entity_id)
    assert isinstance(entity, DaikinClimate)
    point = coordinator.data[entity._device_id].management_point(entity._embedded_id)
    assert point is not None and point.operation_mode is not None
    assert entity.target_temperature_step == 0.5
    assert entity.min_temp == 10
    assert entity.max_temp == 30

    point.operation_mode.value = "fanOnly"
    coordinator.async_update_listeners()

    assert entity.target_temperature_step is None
    assert entity.min_temp == 7
    assert entity.max_temp == 35


def _make_vertical_swing_read_only(point: ManagementPoint) -> None:
    """Make vertical swing unavailable for the climate service test."""
    assert point.climate_control is not None
    fan_operation = point.climate_control.fan_operation()
    assert fan_operation is not None and fan_operation.fan_direction is not None
    assert fan_operation.fan_direction.vertical is not None
    fan_operation.fan_direction.vertical.current_mode.settable = False


def _make_horizontal_swing_read_only(point: ManagementPoint) -> None:
    """Make horizontal swing unavailable for the climate service test."""
    assert point.climate_control is not None
    fan_operation = point.climate_control.fan_operation()
    assert fan_operation is not None and fan_operation.fan_direction is not None
    assert fan_operation.fan_direction.horizontal is not None
    fan_operation.fan_direction.horizontal.current_mode.settable = False


def _make_powerful_mode_read_only(point: ManagementPoint) -> None:
    """Make boost unavailable for the climate service test."""
    assert point.climate_control is not None
    characteristic = point.climate_control.mode_characteristic("powerfulMode")
    assert characteristic is not None
    characteristic.settable = False


def _set_vertical_swing_on(point: ManagementPoint) -> None:
    """Set the vertical swing state to a writable on value."""
    assert point.climate_control is not None
    fan_operation = point.climate_control.fan_operation()
    assert fan_operation is not None and fan_operation.fan_direction is not None
    assert fan_operation.fan_direction.vertical is not None
    mode = fan_operation.fan_direction.vertical.current_mode
    mode.value = "swing"
    mode.settable = True


def _set_horizontal_swing_on(point: ManagementPoint) -> None:
    """Set the horizontal swing state to a writable on value."""
    assert point.climate_control is not None
    fan_operation = point.climate_control.fan_operation()
    assert fan_operation is not None and fan_operation.fan_direction is not None
    assert fan_operation.fan_direction.horizontal is not None
    mode = fan_operation.fan_direction.horizontal.current_mode
    mode.value = "swing"
    mode.settable = True


@pytest.mark.parametrize(
    ("configure_swing", "service", "argument", "state_attribute"),
    [
        pytest.param(
            _set_vertical_swing_on,
            SERVICE_SET_SWING_MODE,
            "swing_mode",
            ClimateEntityStateAttribute.SWING_MODE,
            id="vertical-swing-write-failure",
        ),
        pytest.param(
            _set_horizontal_swing_on,
            SERVICE_SET_SWING_HORIZONTAL_MODE,
            "swing_horizontal_mode",
            ClimateEntityStateAttribute.SWING_HORIZONTAL_MODE,
            id="horizontal-swing-write-failure",
        ),
    ],
)
async def test_climate_swing_write_failure_preserves_entity_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
    configure_swing: Callable[[ManagementPoint], None],
    service: str,
    argument: str,
    state_attribute: ClimateEntityStateAttribute,
) -> None:
    """A failed swing write leaves the published state unchanged."""
    entity_id, _, point, coordinator = await _async_setup_climate_service_fixture(
        hass, config_entry, entity_registry
    )
    configure_swing(point)
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    original_swing_state = state.attributes[state_attribute]
    mock_onecta_client.patch_characteristic.side_effect = OnectaConnectionError(
        "test connection failure", method="PATCH", path="/test"
    )

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id, argument: SWING_OFF},
            blocking=True,
        )

    assert err.value.translation_key == "set_swing_mode_failed"
    state_after_failure = hass.states.get(entity_id)
    assert state_after_failure is not None
    assert state_after_failure.attributes[state_attribute] == original_swing_state


async def test_climate_entities_are_deduplicated_by_management_point(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Create one climate entity per supported target on a real gateway."""
    await _async_setup_fixture(hass, config_entry, "altherma")

    assert set(hass.states.async_entity_ids(CLIMATE_DOMAIN)) == {
        "climate.altherma_room_temperature",
        "climate.altherma_leaving_water_temperature",
        "climate.test_bedroom_1_room_temperature",
        "climate.test_bedroom_2_room_temperature",
        "climate.test_living_room_room_temperature",
        "climate.test_office_room_temperature",
    }


def _offset_gateway_and_point(fixture: str) -> tuple[GatewayDevice, ManagementPoint]:
    """Find a fixture point that advertises the offset setpoint."""
    return next(
        (gateway, point)
        for gateway in _load_gateway_devices(fixture)
        for point in gateway.management_points_by_type("climateControl")
        if point.climate_control is not None
        and LEAVING_WATER_OFFSET in point.climate_control.setpoint_types
    )


@pytest.mark.parametrize(
    ("fixture", "has_offset_climate"),
    [
        pytest.param("altherma3m", True, id="offset-only-altherma"),
        pytest.param("mc80z", True, id="offset-only-purifier"),
        pytest.param("altherma", False, id="room-and-leaving-water"),
        pytest.param("altherma_boost", False, id="multiple-setpoint-types"),
        pytest.param("altherma_schedule", False, id="scheduled-altherma"),
        pytest.param("nomodel_id", False, id="missing-model-id"),
    ],
)
async def test_leaving_water_offset_climate_entity_ownership(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    fixture: str,
    has_offset_climate: bool,
) -> None:
    """Keep offset climate ownership only when it is the point's sole target."""
    gateway, point = _offset_gateway_and_point(fixture)
    await _async_setup_fixture(hass, config_entry, fixture)

    entity_id = entity_registry.async_get_entity_id(
        CLIMATE_DOMAIN,
        DOMAIN,
        f"{gateway.id}_{point.embedded_id}_{LEAVING_WATER_OFFSET}",
    )
    assert (entity_id is not None) is has_offset_climate


async def test_offset_climate_becomes_unavailable_when_another_target_appears(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Hide the offset climate entity if another target appears after setup."""
    gateway, point = _offset_gateway_and_point("altherma3m")
    await _async_setup_fixture(hass, config_entry, "altherma3m")
    coordinator = config_entry.runtime_data
    offset_entity_id = entity_registry.async_get_entity_id(
        CLIMATE_DOMAIN,
        DOMAIN,
        f"{gateway.id}_{point.embedded_id}_{LEAVING_WATER_OFFSET}",
    )
    assert offset_entity_id is not None

    updated_gateway = _load_gateway_devices("altherma3m")[0]
    updated_point = updated_gateway.management_point(point.embedded_id)
    assert updated_point is not None and updated_point.temperature_control is not None
    operation_modes = updated_point.temperature_control.value.operation_modes
    offset = operation_modes["heating"].setpoints[LEAVING_WATER_OFFSET]
    for operation_mode in operation_modes.values():
        operation_mode.setpoints["leavingWaterTemperature"] = replace(offset, value=45)

    mock_onecta_client.get_gateway_devices.return_value = [updated_gateway]
    await _async_fire_coordinator_update(hass, coordinator, freezer)

    state = hass.states.get(offset_entity_id)
    assert state is not None and state.state == "unavailable"
    assert (
        entity_registry.async_get_entity_id(
            CLIMATE_DOMAIN,
            DOMAIN,
            f"{gateway.id}_{point.embedded_id}_leavingWaterTemperature",
        )
        is not None
    )


@pytest.mark.parametrize(
    "fixture",
    [
        pytest.param("altherma3m", id="altherma"),
        pytest.param("mc80z", id="purifier"),
    ],
)
async def test_offset_only_climate_has_mode_controls_without_temperature_target(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    fixture: str,
) -> None:
    """Expose controller modes without treating an offset as a target temp."""
    gateway, point = _offset_gateway_and_point(fixture)
    await _async_setup_fixture(hass, config_entry, fixture)
    entity_id = entity_registry.async_get_entity_id(
        CLIMATE_DOMAIN,
        DOMAIN,
        f"{gateway.id}_{point.embedded_id}_{LEAVING_WATER_OFFSET}",
    )
    assert entity_id is not None
    entity = hass.data[CLIMATE_DOMAIN].get_entity(entity_id)
    assert isinstance(entity, DaikinClimate)
    state = hass.states.get(entity_id)
    assert state is not None
    assert ClimateEntityStateAttribute.TARGET_TEMPERATURE not in state.attributes
    assert ClimateEntityCapabilityAttribute.TARGET_TEMP_STEP not in state.attributes
    assert state.attributes[ATTR_MIN_TEMP] == DEFAULT_MIN_TEMP
    assert state.attributes[ATTR_MAX_TEMP] == DEFAULT_MAX_TEMP
    assert ClimateEntityStateAttribute.CURRENT_TEMPERATURE in state.attributes
    assert entity.target_temperature is None
    assert entity.target_temperature_step is None
    assert not hasattr(entity, "_attr_min_temp")
    assert not hasattr(entity, "_attr_max_temp")
    supported_features = state.attributes["supported_features"]
    assert supported_features & ClimateEntityFeature.TARGET_TEMPERATURE == 0
    assert supported_features & ClimateEntityFeature.TURN_ON
    assert supported_features & ClimateEntityFeature.TURN_OFF
    assert state.attributes[ClimateEntityCapabilityAttribute.HVAC_MODES]


async def test_offset_only_climate_supports_hvac_mode_but_not_set_temperature(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Keep HVAC control while rejecting absolute-temperature writes."""
    gateway = _load_gateway_devices("altherma3m")[0]
    point = next(
        point
        for point in gateway.management_points_by_type("climateControl")
        if point.climate_control is not None
        and LEAVING_WATER_OFFSET in point.climate_control.setpoint_types
    )
    await _async_setup_fixture(hass, config_entry, "altherma3m")
    entity_id = entity_registry.async_get_entity_id(
        CLIMATE_DOMAIN,
        DOMAIN,
        f"{gateway.id}_{point.embedded_id}_{LEAVING_WATER_OFFSET}",
    )
    assert entity_id is not None
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, "hvac_mode": HVACMode.HEAT},
        blocking=True,
    )
    mock_onecta_client.patch_characteristic.assert_awaited_once_with(
        gateway.id, point.embedded_id, "onOffMode", "on", path=None
    )

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: entity_id,
                ClimateServiceArgument.TEMPERATURE: 5,
            },
            blocking=True,
        )
    assert err.value.translation_key == "service_not_supported"
    mock_onecta_client.patch_characteristic.assert_awaited_once()


async def test_climate_platform_skips_points_without_climate_controls(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Do not create climate entities for a gateway without climate controls."""
    await _async_setup_fixture(hass, config_entry, "homehub")

    assert hass.states.async_entity_ids(CLIMATE_DOMAIN) == []


def _keep_climate_available(
    _coordinator: OnectaDataUpdateCoordinator,
    _device: DaikinOnectaDevice,
    _management_point: ManagementPoint,
) -> None:
    """Keep the climate fixture available."""


def _fail_climate_coordinator(
    coordinator: OnectaDataUpdateCoordinator,
    _device: DaikinOnectaDevice,
    _management_point: ManagementPoint,
) -> None:
    """Mark the climate coordinator unavailable."""
    coordinator.last_update_success = False


def _fail_climate_gateway(
    _coordinator: OnectaDataUpdateCoordinator,
    device: DaikinOnectaDevice,
    _management_point: ManagementPoint,
) -> None:
    """Mark the climate gateway unavailable."""
    device.mark_unavailable()


def _remove_climate_management_point(
    _coordinator: OnectaDataUpdateCoordinator,
    device: DaikinOnectaDevice,
    management_point: ManagementPoint,
) -> None:
    """Remove the climate management point from its gateway."""
    device.device.management_points.remove(management_point)


def _replace_test_management_point(
    device: DaikinOnectaDevice,
    previous: ManagementPoint,
    replacement: ManagementPoint,
) -> None:
    """Replace one management point on the wrapped gateway model."""
    device.device.management_points.remove(previous)
    device.device.management_points.append(replacement)
    device.set_device_data(device.device)


def _set_missing_power_state(
    device: DaikinOnectaDevice, management_point: ManagementPoint
) -> None:
    """Remove the power characteristic while retaining an active operation mode."""
    replacement = replace(management_point, on_off_mode=None)
    assert replacement.operation_mode is not None
    replacement.operation_mode.value = "auto"
    _replace_test_management_point(device, management_point, replacement)


def _set_unknown_power_state(
    _device: DaikinOnectaDevice, management_point: ManagementPoint
) -> None:
    """Set the existing power characteristic to an unknown value."""
    assert management_point.climate_control is not None
    assert management_point.climate_control.on_off_mode is not None
    management_point.climate_control.on_off_mode.value = None


def _set_missing_operation_state(
    device: DaikinOnectaDevice, management_point: ManagementPoint
) -> None:
    """Remove the operation-mode characteristic while power remains on."""
    assert management_point.climate_control is not None
    assert management_point.climate_control.on_off_mode is not None
    management_point.climate_control.on_off_mode.value = "on"
    replacement = replace(management_point, operation_mode=None)
    _replace_test_management_point(device, management_point, replacement)


def _set_omitted_operation_state(
    _device: DaikinOnectaDevice, management_point: ManagementPoint
) -> None:
    """Keep operation mode present but omit its current value."""
    assert management_point.climate_control is not None
    assert management_point.climate_control.on_off_mode is not None
    assert management_point.climate_control.operation_mode is not None
    management_point.climate_control.on_off_mode.value = "on"
    management_point.climate_control.operation_mode.value = None


def _remove_fan_control(management_point: ManagementPoint) -> None:
    """Remove fan control from a climate point."""
    management_point.fan_control = None


def _set_fan_speed_read_only(management_point: ManagementPoint) -> None:
    """Make fan speed telemetry read-only."""
    assert management_point.climate_control is not None
    fan_operation = management_point.climate_control.fan_operation()
    assert fan_operation is not None and fan_operation.fan_speed is not None
    fan_operation.fan_speed.current_mode.settable = False


def _set_vertical_swing_read_only(management_point: ManagementPoint) -> None:
    """Make vertical swing telemetry read-only."""
    assert management_point.climate_control is not None
    fan_operation = management_point.climate_control.fan_operation()
    assert fan_operation is not None and fan_operation.fan_direction is not None
    assert fan_operation.fan_direction.vertical is not None
    fan_operation.fan_direction.vertical.current_mode.settable = False


def _set_horizontal_swing_read_only(management_point: ManagementPoint) -> None:
    """Make horizontal swing telemetry read-only."""
    assert management_point.climate_control is not None
    fan_operation = management_point.climate_control.fan_operation()
    assert fan_operation is not None and fan_operation.fan_direction is not None
    assert fan_operation.fan_direction.horizontal is not None
    fan_operation.fan_direction.horizontal.current_mode.settable = False


def _get_fan_speed_modes(
    management_point: ManagementPoint,
) -> tuple[Characteristic, Characteristic]:
    """Return heating and cooling fan-speed modes."""
    assert management_point.climate_control is not None
    heating = management_point.climate_control.fan_operation("heating")
    cooling = management_point.climate_control.fan_operation("cooling")
    assert heating is not None and heating.fan_speed is not None
    assert cooling is not None and cooling.fan_speed is not None
    return heating.fan_speed.current_mode, cooling.fan_speed.current_mode


def _get_vertical_swing_modes(
    management_point: ManagementPoint,
) -> tuple[Characteristic, Characteristic]:
    """Return heating and cooling vertical-swing modes."""
    assert management_point.climate_control is not None
    heating = management_point.climate_control.fan_operation("heating")
    cooling = management_point.climate_control.fan_operation("cooling")
    assert heating is not None and heating.fan_direction is not None
    assert cooling is not None and cooling.fan_direction is not None
    assert heating.fan_direction.vertical is not None
    assert cooling.fan_direction.vertical is not None
    return (
        heating.fan_direction.vertical.current_mode,
        cooling.fan_direction.vertical.current_mode,
    )


@pytest.mark.parametrize(
    ("apply_failure", "expected_available"),
    [
        pytest.param(_keep_climate_available, True, id="available"),
        pytest.param(_fail_climate_coordinator, False, id="coordinator"),
        pytest.param(_fail_climate_gateway, False, id="gateway"),
        pytest.param(_remove_climate_management_point, False, id="management-point"),
    ],
)
async def test_climate_entity_availability(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    apply_failure: Callable[
        [OnectaDataUpdateCoordinator, DaikinOnectaDevice, ManagementPoint], None
    ],
    expected_available: bool,
) -> None:
    """Reflect coordinator and cloud device availability in the entity state."""
    (
        entity_id,
        _,
        management_point,
        coordinator,
    ) = await _async_setup_climate_service_fixture(hass, config_entry, entity_registry)
    device = next(iter(coordinator.data.values()))
    apply_failure(coordinator, device, management_point)
    coordinator.async_update_listeners()

    state = hass.states.get(entity_id)
    assert state is not None
    assert (state.state != "unavailable") is expected_available


async def test_climate_service_sets_fixed_fan_speed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Set a fixed fan speed through Home Assistant's climate service."""
    (
        entity_id,
        gateway_id,
        management_point,
        _coordinator,
    ) = await _async_setup_climate_service_fixture(hass, config_entry, entity_registry)
    climate_control = management_point.climate_control
    assert climate_control is not None
    fan_operation = climate_control.fan_operation()
    assert fan_operation is not None and fan_operation.fan_speed is not None
    assert fan_operation.fan_speed.modes is not None
    fixed_mode = fan_operation.fan_speed.modes[FANMODE_FIXED]
    initial_speed = fixed_mode.value

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: entity_id, "fan_mode": str(initial_speed + 1)},
        blocking=True,
    )

    mock_onecta_client.patch_characteristic.assert_awaited_once_with(
        gateway_id,
        management_point.embedded_id,
        "fanControl",
        initial_speed + 1,
        path="/operationModes/heating/fanSpeed/modes/fixed",
    )
    assert fixed_mode.value == initial_speed + 1
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[ClimateEntityStateAttribute.FAN_MODE] == str(
        initial_speed + 1
    )


async def test_climate_service_reselects_read_only_fixed_fan_speed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Allow selecting the current read-only fixed speed as a no-op."""
    (
        entity_id,
        _,
        management_point,
        coordinator,
    ) = await _async_setup_climate_service_fixture(hass, config_entry, entity_registry)
    climate_control = management_point.climate_control
    assert climate_control is not None
    fan_operation = climate_control.fan_operation()
    assert fan_operation is not None and fan_operation.fan_speed is not None
    assert fan_operation.fan_speed.modes is not None
    fan_operation.fan_speed.current_mode.value = FANMODE_FIXED
    fixed_mode = fan_operation.fan_speed.modes[FANMODE_FIXED]
    fixed_mode.settable = False
    coordinator.async_update_listeners()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: entity_id, "fan_mode": str(fixed_mode.value)},
        blocking=True,
    )

    mock_onecta_client.patch_characteristic.assert_not_awaited()


async def test_climate_service_sets_fixed_mode_on_replaced_model(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Update the current model when a fixed-mode command replaces the model."""
    (
        entity_id,
        gateway_id,
        management_point,
        coordinator,
    ) = await _async_setup_climate_service_fixture(hass, config_entry, entity_registry)
    climate_control = management_point.climate_control
    assert climate_control is not None
    fan_operation = climate_control.fan_operation()
    assert fan_operation is not None and fan_operation.fan_speed is not None
    assert fan_operation.fan_speed.modes is not None
    fixed_mode = fan_operation.fan_speed.modes[FANMODE_FIXED]
    target_speed = fixed_mode.value
    fan_operation.fan_speed.current_mode.value = "auto"
    coordinator.async_update_listeners()
    device = coordinator.data[gateway_id]
    old_current_mode = fan_operation.fan_speed.current_mode

    async def replace_device_model(*_args: object, **_kwargs: object) -> None:
        device.set_device_data(deepcopy(device.device))
        current_management_point = device.management_point(management_point.embedded_id)
        assert current_management_point is not None
        current_climate_control = current_management_point.climate_control
        assert current_climate_control is not None
        current_fan_operation = current_climate_control.fan_operation()
        assert current_fan_operation is not None and current_fan_operation.fan_speed
        assert current_fan_operation.fan_speed.modes is not None
        current_fan_operation.fan_speed.modes[FANMODE_FIXED].value = target_speed + 1

    mock_onecta_client.patch_characteristic.side_effect = replace_device_model

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {ATTR_ENTITY_ID: entity_id, "fan_mode": str(target_speed)},
        blocking=True,
    )

    current_management_point = device.management_point(management_point.embedded_id)
    assert current_management_point is not None
    current_climate_control = current_management_point.climate_control
    assert current_climate_control is not None
    current_fan_operation = current_climate_control.fan_operation()
    assert (
        current_fan_operation is not None
        and current_fan_operation.fan_speed is not None
    )
    assert current_fan_operation.fan_speed.modes is not None
    assert old_current_mode.value == "auto"
    assert current_fan_operation.fan_speed.current_mode.value == FANMODE_FIXED
    assert current_fan_operation.fan_speed.modes[FANMODE_FIXED].value == target_speed
    assert mock_onecta_client.patch_characteristic.await_args_list == [
        call(
            gateway_id,
            management_point.embedded_id,
            "fanControl",
            FANMODE_FIXED,
            path="/operationModes/heating/fanSpeed/currentMode",
        ),
        call(
            gateway_id,
            management_point.embedded_id,
            "fanControl",
            target_speed,
            path="/operationModes/heating/fanSpeed/modes/fixed",
        ),
    ]
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[ClimateEntityStateAttribute.FAN_MODE] == str(target_speed)


@pytest.mark.parametrize(
    ("preset_mode", "native_characteristic"),
    [(PRESET_AWAY, "holidayMode"), (PRESET_BOOST, "powerfulMode")],
)
async def test_climate_service_toggles_presets(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
    preset_mode: str,
    native_characteristic: str,
) -> None:
    """Enable and disable both preset types through Home Assistant services."""
    (
        entity_id,
        gateway_id,
        management_point,
        coordinator,
    ) = await _async_setup_climate_service_fixture(hass, config_entry, entity_registry)
    climate_control = management_point.climate_control
    assert climate_control is not None
    assert climate_control.on_off_mode is not None
    assert climate_control.operation_mode is not None
    climate_control.on_off_mode.value = "on"
    climate_control.operation_mode.value = "heating"
    holiday_mode = climate_control.mode_characteristic("holidayMode")
    powerful_mode = climate_control.mode_characteristic("powerfulMode")
    assert holiday_mode is not None and powerful_mode is not None
    coordinator.async_update_listeners()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, "preset_mode": preset_mode},
        blocking=True,
    )

    preset_values = {
        "holidayMode": holiday_mode.value.enabled,
        "powerfulMode": powerful_mode.value,
    }
    enabled_value = preset_values[native_characteristic]
    assert enabled_value in {True, "on"}
    state = hass.states.get(entity_id)
    assert (
        state is not None and state.attributes[ClimateEntityStateAttribute.PRESET_MODE]
    )
    assert state.attributes[ClimateEntityStateAttribute.PRESET_MODE] == preset_mode

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, "preset_mode": PRESET_NONE},
        blocking=True,
    )

    preset_values = {
        "holidayMode": holiday_mode.value.enabled,
        "powerfulMode": powerful_mode.value,
    }
    disabled_value = preset_values[native_characteristic]
    assert disabled_value in {False, "off"}
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[ClimateEntityStateAttribute.PRESET_MODE] == PRESET_NONE
    assert (
        mock_onecta_client.post_management_point.await_count
        == {
            "holidayMode": 2,
            "powerfulMode": 0,
        }[native_characteristic]
    )
    assert (
        mock_onecta_client.patch_characteristic.await_count
        == {
            "holidayMode": 0,
            "powerfulMode": 2,
        }[native_characteristic]
    )
    expected_post_prefix = {
        "holidayMode": [
            (gateway_id, management_point.embedded_id, "holiday-mode"),
            (gateway_id, management_point.embedded_id, "holiday-mode"),
        ],
        "powerfulMode": [],
    }
    assert [
        call_args.args[:3]
        for call_args in mock_onecta_client.post_management_point.await_args_list
    ] == expected_post_prefix[native_characteristic]
    expected_patch_prefix = {
        "holidayMode": [],
        "powerfulMode": [
            (gateway_id, management_point.embedded_id, native_characteristic),
            (gateway_id, management_point.embedded_id, native_characteristic),
        ],
    }
    assert [
        call_args.args[:3]
        for call_args in mock_onecta_client.patch_characteristic.await_args_list
    ] == expected_patch_prefix[native_characteristic]


async def test_climate_service_clears_all_active_presets(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Clear every active preset when switching to none."""
    (
        entity_id,
        gateway_id,
        management_point,
        coordinator,
    ) = await _async_setup_climate_service_fixture(hass, config_entry, entity_registry)
    climate_control = management_point.climate_control
    assert climate_control is not None
    management_point.characteristics["econoMode"] = Characteristic(
        value="on", settable=True, values=["on", "off"]
    )
    powerful_mode = climate_control.mode_characteristic("powerfulMode")
    econo_mode = climate_control.mode_characteristic("econoMode")
    assert powerful_mode is not None and econo_mode is not None
    powerful_mode.value = "on"
    powerful_mode.settable = True
    econo_mode.value = "on"
    econo_mode.settable = True
    coordinator.async_update_listeners()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, "preset_mode": PRESET_NONE},
        blocking=True,
    )

    assert powerful_mode.value == "off"
    assert econo_mode.value == "off"
    assert mock_onecta_client.patch_characteristic.await_args_list == [
        call(
            gateway_id,
            management_point.embedded_id,
            "powerfulMode",
            "off",
            path=None,
        ),
        call(
            gateway_id,
            management_point.embedded_id,
            "econoMode",
            "off",
            path=None,
        ),
    ]


async def test_climate_keeps_requested_active_preset(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Keep an already-active requested preset while disabling another one."""
    (
        entity_id,
        gateway_id,
        management_point,
        coordinator,
    ) = await _async_setup_climate_service_fixture(hass, config_entry, entity_registry)
    climate_control = management_point.climate_control
    assert climate_control is not None
    assert climate_control.on_off_mode is not None
    holiday_mode = climate_control.mode_characteristic("holidayMode")
    powerful_mode = climate_control.mode_characteristic("powerfulMode")
    assert holiday_mode is not None and powerful_mode is not None
    climate_control.on_off_mode.value = "on"
    holiday_mode.value.enabled = True
    holiday_mode.settable = True
    powerful_mode.value = "on"
    powerful_mode.settable = True
    coordinator.async_update_listeners()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, "preset_mode": PRESET_AWAY},
        blocking=True,
    )

    assert holiday_mode.value.enabled
    assert powerful_mode.value == "off"
    mock_onecta_client.patch_characteristic.assert_awaited_once_with(
        gateway_id,
        management_point.embedded_id,
        "powerfulMode",
        "off",
        path=None,
    )


@pytest.mark.parametrize(
    ("target_preset", "initial_value", "expected_state", "expected_value"),
    [
        (PRESET_BOOST, "off", PRESET_NONE, "on"),
        (PRESET_NONE, "on", PRESET_BOOST, "off"),
    ],
)
async def test_climate_service_preset_failure_keeps_cached_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
    target_preset: str,
    initial_value: str,
    expected_state: str,
    expected_value: str,
) -> None:
    """Leave the cached preset unchanged when Daikin rejects its command."""
    (
        entity_id,
        gateway_id,
        management_point,
        coordinator,
    ) = await _async_setup_climate_service_fixture(hass, config_entry, entity_registry)
    climate_control = management_point.climate_control
    assert climate_control is not None
    assert climate_control.on_off_mode is not None
    assert climate_control.operation_mode is not None
    climate_control.on_off_mode.value = "on"
    climate_control.operation_mode.value = "heating"
    powerful_mode = climate_control.mode_characteristic("powerfulMode")
    assert powerful_mode is not None
    powerful_mode.value = initial_value
    coordinator.async_update_listeners()
    mock_onecta_client.patch_characteristic.side_effect = OnectaConnectionError(
        "test connection failure", method="PATCH", path="/test"
    )

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: entity_id, "preset_mode": target_preset},
            blocking=True,
        )

    assert err.value.translation_key == "set_preset_mode_failed"
    assert powerful_mode.value == initial_value
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[ClimateEntityStateAttribute.PRESET_MODE] == expected_state
    mock_onecta_client.patch_characteristic.assert_awaited_once_with(
        gateway_id,
        management_point.embedded_id,
        "powerfulMode",
        expected_value,
        path=None,
    )


async def test_climate_service_does_not_publish_after_management_point_disappears(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Do not publish a power write after its management point disappears."""
    (
        entity_id,
        _,
        management_point,
        _coordinator,
    ) = await _async_setup_climate_service_fixture(hass, config_entry, entity_registry)
    assert management_point.on_off_mode is not None
    assert management_point.on_off_mode.value == "off"
    device = next(iter(config_entry.runtime_data.data.values()))

    async def remove_management_point(*_args, **_kwargs) -> None:
        device.device.management_points.remove(management_point)

    mock_onecta_client.patch_characteristic.side_effect = remove_management_point

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_onecta_client.patch_characteristic.assert_awaited_once()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == HVACMode.OFF


async def test_climate_service_publishes_power_before_mode_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Keep a successful power stage visible when the mode stage fails."""
    (
        entity_id,
        gateway_id,
        management_point,
        coordinator,
    ) = await _async_setup_climate_service_fixture(hass, config_entry, entity_registry)
    climate_control = management_point.climate_control
    assert climate_control is not None
    assert climate_control.on_off_mode is not None
    assert climate_control.operation_mode is not None
    climate_control.on_off_mode.value = "off"
    climate_control.operation_mode.value = "cooling"
    coordinator.async_update_listeners()
    mock_onecta_client.patch_characteristic.side_effect = [
        None,
        OnectaConnectionError("test connection failure", method="PATCH", path="/test"),
    ]

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: entity_id, "hvac_mode": HVACMode.HEAT},
            blocking=True,
        )

    assert err.value.translation_key == "set_hvac_mode_failed"
    assert mock_onecta_client.patch_characteristic.await_args_list[0].args == (
        gateway_id,
        management_point.embedded_id,
        "onOffMode",
        "on",
    )
    assert mock_onecta_client.patch_characteristic.await_args_list[1].args == (
        gateway_id,
        management_point.embedded_id,
        "operationMode",
        "heating",
    )
    assert climate_control.on_off_mode.value == "on"
    assert climate_control.operation_mode.value == "cooling"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == HVACMode.COOL


async def test_climate_service_updates_replaced_management_point(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Apply subsequent writes to the cloud model replaced during a command."""
    (
        entity_id,
        gateway_id,
        management_point,
        coordinator,
    ) = await _async_setup_climate_service_fixture(hass, config_entry, entity_registry)
    climate_control = management_point.climate_control
    assert climate_control is not None
    assert climate_control.on_off_mode is not None
    assert climate_control.operation_mode is not None
    climate_control.on_off_mode.value = "off"
    climate_control.operation_mode.value = "heating"
    coordinator.async_update_listeners()
    device = coordinator.data[gateway_id]
    old_device_model = device.device

    async def replace_device_model(*_args, **_kwargs) -> None:
        device.set_device_data(deepcopy(device.device))

    mock_onecta_client.patch_characteristic.side_effect = replace_device_model

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, "hvac_mode": HVACMode.COOL},
        blocking=True,
    )

    current_management_point = device.management_point(management_point.embedded_id)
    assert current_management_point is not None
    current_climate_control = current_management_point.climate_control
    assert current_climate_control is not None
    assert current_climate_control.on_off_mode is not None
    assert current_climate_control.operation_mode is not None
    assert management_point.on_off_mode.value == "off"
    assert management_point.operation_mode.value == "heating"
    assert current_climate_control.on_off_mode.value == "on"
    assert current_climate_control.operation_mode.value == "cooling"
    assert len(mock_onecta_client.patch_characteristic.await_args_list) == 2
    assert mock_onecta_client.patch_characteristic.await_args_list[0].args == (
        gateway_id,
        management_point.embedded_id,
        "onOffMode",
        "on",
    )
    assert mock_onecta_client.patch_characteristic.await_args_list[1].args == (
        gateway_id,
        management_point.embedded_id,
        "operationMode",
        "cooling",
    )
    assert device.device is not old_device_model


async def test_climate_service_uses_advertised_native_hvac_mode(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Use the advertised native Daikin mode through the climate service."""
    (
        entity_id,
        gateway_id,
        management_point,
        coordinator,
    ) = await _async_setup_climate_service_fixture(hass, config_entry, entity_registry)
    climate_control = management_point.climate_control
    assert climate_control is not None
    operation_mode = climate_control.operation_mode
    assert operation_mode is not None
    operation_mode.value = "cooling"
    operation_mode.values = ["cooling", "heatingNight"]
    assert climate_control.on_off_mode is not None
    climate_control.on_off_mode.value = "on"
    coordinator.async_update_listeners()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, "hvac_mode": HVACMode.HEAT},
        blocking=True,
    )

    mock_onecta_client.patch_characteristic.assert_awaited_once_with(
        gateway_id,
        management_point.embedded_id,
        "operationMode",
        "heatingNight",
        path=None,
    )
    assert operation_mode.value == "heatingNight"


async def test_climate_service_sets_operation_mode_off_without_power_control(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Use operationMode to turn off and on when there is no power control."""
    (
        entity_id,
        gateway_id,
        management_point,
        coordinator,
    ) = await _async_setup_climate_service_fixture(hass, config_entry, entity_registry)
    climate_control = management_point.climate_control
    assert climate_control is not None
    replacement = replace(management_point, on_off_mode=None)
    _replace_test_management_point(
        coordinator.data[gateway_id], management_point, replacement
    )
    management_point = replacement
    climate_control = management_point.climate_control
    assert climate_control is not None
    assert climate_control.operation_mode is not None
    climate_control.operation_mode.value = "heating"
    climate_control.operation_mode.values = ["cooling", "heating", "off"]
    coordinator.async_update_listeners()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, "hvac_mode": HVACMode.OFF},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == HVACMode.OFF
    assert mock_onecta_client.patch_characteristic.await_args_list[-1].args == (
        gateway_id,
        management_point.embedded_id,
        "operationMode",
        "off",
    )

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, "hvac_mode": HVACMode.HEAT},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == HVACMode.HEAT
    assert mock_onecta_client.patch_characteristic.await_args_list[-1].args == (
        gateway_id,
        management_point.embedded_id,
        "operationMode",
        "heating",
    )
    assert mock_onecta_client.patch_characteristic.await_count == 2


async def test_climate_service_rejects_unknown_native_mode(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Reject a Daikin mode with no Home Assistant equivalent before writing."""
    (
        entity_id,
        _,
        management_point,
        coordinator,
    ) = await _async_setup_climate_service_fixture(hass, config_entry, entity_registry)
    climate_control = management_point.climate_control
    assert climate_control is not None
    assert climate_control.operation_mode is not None
    climate_control.operation_mode.value = "vendorMode"
    climate_control.operation_mode.values = ["vendorMode"]
    assert climate_control.on_off_mode is not None
    climate_control.on_off_mode.value = "on"
    coordinator.async_update_listeners()

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: entity_id, "hvac_mode": HVACMode.HEAT},
            blocking=True,
        )

    assert err.value.translation_key == "not_valid_hvac_mode"
    mock_onecta_client.patch_characteristic.assert_not_awaited()


@pytest.mark.parametrize(
    ("configure_state", "expected_state"),
    [
        pytest.param(_set_missing_power_state, HVACMode.HEAT_COOL, id="missing-power"),
        pytest.param(_set_unknown_power_state, "unknown", id="unknown-power"),
        pytest.param(_set_missing_operation_state, "unknown", id="missing-operation"),
        pytest.param(_set_omitted_operation_state, "unknown", id="omitted-operation"),
    ],
)
async def test_climate_state_handles_missing_hvac_data(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    configure_state: Callable[[DaikinOnectaDevice, ManagementPoint], None],
    expected_state: str,
) -> None:
    """Expose omitted and malformed power/mode data through HA entity state."""
    (
        entity_id,
        _,
        management_point,
        coordinator,
    ) = await _async_setup_climate_service_fixture(hass, config_entry, entity_registry)
    climate_control = management_point.climate_control
    assert climate_control is not None
    assert climate_control.operation_mode is not None
    device = next(iter(coordinator.data.values()))
    configure_state(device, management_point)
    coordinator.async_update_listeners()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state


async def test_climate_state_advertises_read_only_off_mode(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Advertise the observed off state even without writable power control."""
    (
        entity_id,
        _,
        management_point,
        coordinator,
    ) = await _async_setup_climate_service_fixture(hass, config_entry, entity_registry)
    climate_control = management_point.climate_control
    assert climate_control is not None and climate_control.on_off_mode is not None
    climate_control.on_off_mode.value = "off"
    climate_control.on_off_mode.settable = False
    assert climate_control.operation_mode is not None
    climate_control.operation_mode.settable = False
    coordinator.async_update_listeners()

    state = hass.states.get(entity_id)
    entity = hass.data[CLIMATE_DOMAIN].get_entity(entity_id)
    assert state is not None and entity is not None
    assert state.state == HVACMode.OFF
    assert HVACMode.OFF in entity.hvac_modes


async def test_climate_service_publishes_fixed_mode_before_speed_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Publish the fixed mode stage when the subsequent speed write fails."""
    (
        entity_id,
        gateway_id,
        management_point,
        coordinator,
    ) = await _async_setup_climate_service_fixture(hass, config_entry, entity_registry)
    climate_control = management_point.climate_control
    assert climate_control is not None
    fan_operation = climate_control.fan_operation()
    assert fan_operation is not None and fan_operation.fan_speed is not None
    assert fan_operation.fan_speed.modes is not None
    fan_operation.fan_speed.current_mode.value = "quiet"
    fixed_mode = fan_operation.fan_speed.modes[FANMODE_FIXED]
    initial_speed = fixed_mode.value
    mock_onecta_client.patch_characteristic.side_effect = [
        None,
        OnectaConnectionError("test connection failure", method="PATCH", path="/test"),
    ]
    coordinator.async_update_listeners()

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: entity_id, "fan_mode": str(initial_speed + 1)},
            blocking=True,
        )

    assert err.value.translation_key == "set_fan_mode_failed"
    assert mock_onecta_client.patch_characteristic.await_args_list[0].args == (
        gateway_id,
        management_point.embedded_id,
        "fanControl",
        FANMODE_FIXED,
    )
    assert mock_onecta_client.patch_characteristic.await_args_list[1].args == (
        gateway_id,
        management_point.embedded_id,
        "fanControl",
        initial_speed + 1,
    )
    assert fixed_mode.value == initial_speed
    assert fan_operation.fan_speed.current_mode.value == FANMODE_FIXED
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[ClimateEntityStateAttribute.FAN_MODE] == str(initial_speed)


@pytest.mark.parametrize(
    (
        "service",
        "argument",
        "value",
        "path",
        "get_modes",
        "expected_command",
    ),
    [
        (
            SERVICE_SET_FAN_MODE,
            "fan_mode",
            "quiet",
            "/operationModes/heating/fanSpeed/currentMode",
            _get_fan_speed_modes,
            "quiet",
        ),
        (
            SERVICE_SET_SWING_MODE,
            "swing_mode",
            SWING_ON,
            "/operationModes/heating/fanDirection/vertical/currentMode",
            _get_vertical_swing_modes,
            "swing",
        ),
    ],
)
async def test_climate_service_keeps_captured_operation_mode(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
    service: str,
    argument: str,
    value: str,
    path: str,
    get_modes: Callable[[ManagementPoint], tuple[Characteristic, Characteristic]],
    expected_command: str,
) -> None:
    """A live mode change during a command does not redirect its cache write."""
    (
        entity_id,
        gateway_id,
        management_point,
        _coordinator,
    ) = await _async_setup_climate_service_fixture(hass, config_entry, entity_registry)
    climate_control = management_point.climate_control
    assert climate_control is not None
    assert management_point.operation_mode is not None
    management_point.operation_mode.value = "heating"
    captured_mode, active_mode = get_modes(management_point)
    captured_value = captured_mode.value
    active_value = active_mode.value

    def replace_active_mode(*_args, **_kwargs) -> None:
        assert management_point.operation_mode is not None
        management_point.operation_mode.value = "cooling"

    mock_onecta_client.patch_characteristic.side_effect = replace_active_mode
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id, argument: value},
        blocking=True,
    )

    mock_onecta_client.patch_characteristic.assert_awaited_once_with(
        gateway_id,
        management_point.embedded_id,
        "fanControl",
        expected_command,
        path=path,
    )
    heating_mode, cooling_mode = get_modes(management_point)
    assert heating_mode.value == expected_command
    assert cooling_mode.value == active_value
    assert captured_value != value


async def test_climate_service_aborts_preset_replacement_after_failed_disable(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Do not enable a replacement preset if disabling the current one fails."""
    (
        entity_id,
        _,
        management_point,
        coordinator,
    ) = await _async_setup_climate_service_fixture(hass, config_entry, entity_registry)
    climate_control = management_point.climate_control
    assert climate_control is not None
    assert climate_control.on_off_mode is not None
    climate_control.on_off_mode.value = "on"
    powerful_mode = climate_control.mode_characteristic("powerfulMode")
    assert powerful_mode is not None
    powerful_mode.value = "on"
    coordinator.async_update_listeners()
    mock_onecta_client.patch_characteristic.side_effect = OnectaConnectionError(
        "test connection failure", method="PATCH", path="/test"
    )

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: entity_id, "preset_mode": PRESET_AWAY},
            blocking=True,
        )

    assert err.value.translation_key == "set_preset_mode_failed"
    assert powerful_mode.value == "on"
    mock_onecta_client.patch_characteristic.assert_awaited_once()
    mock_onecta_client.post_management_point.assert_not_awaited()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[ClimateEntityStateAttribute.PRESET_MODE] == PRESET_BOOST


async def test_climate_service_keeps_hidden_holiday_when_selected_preset_is_current(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Selecting the displayed preset must not disable a hidden active mode."""
    await _async_setup_fixture(hass, config_entry, "gas")
    entity_id = hass.states.async_entity_ids(CLIMATE_DOMAIN)[0]
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[ClimateEntityStateAttribute.PRESET_MODE] == PRESET_BOOST

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: entity_id, "preset_mode": PRESET_BOOST},
        blocking=True,
    )

    mock_onecta_client.patch_characteristic.assert_not_awaited()
    mock_onecta_client.post_management_point.assert_not_awaited()


@pytest.mark.parametrize("power_settable", [False, True])
async def test_climate_state_advertises_writable_power_features(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    power_settable: bool,
) -> None:
    """Advertise on/off features only when Daikin reports writable power."""
    (
        entity_id,
        _,
        management_point,
        coordinator,
    ) = await _async_setup_climate_service_fixture(hass, config_entry, entity_registry)
    climate_control = management_point.climate_control
    assert climate_control is not None and climate_control.on_off_mode is not None
    climate_control.on_off_mode.settable = power_settable
    coordinator.async_update_listeners()

    state = hass.states.get(entity_id)
    assert state is not None
    features = state.attributes[EntityStateAttribute.SUPPORTED_FEATURES]
    assert bool(features & ClimateEntityFeature.TURN_ON) is power_settable
    assert bool(features & ClimateEntityFeature.TURN_OFF) is power_settable


async def test_climate_state_lists_none_before_supported_presets(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Expose the neutral preset first in the real climate entity state."""
    entity_id, _, _, _ = await _async_setup_climate_service_fixture(
        hass, config_entry, entity_registry
    )

    entity = hass.data[CLIMATE_DOMAIN].get_entity(entity_id)
    assert entity is not None
    assert entity.preset_modes[0] == PRESET_NONE


async def test_climate_state_omits_read_only_presets(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Do not advertise preset controls Daikin marks read-only."""
    (
        entity_id,
        _,
        management_point,
        coordinator,
    ) = await _async_setup_climate_service_fixture(hass, config_entry, entity_registry)
    climate_control = management_point.climate_control
    assert climate_control is not None
    for name in ("holidayMode", "powerfulMode"):
        preset = climate_control.mode_characteristic(name)
        assert preset is not None
        preset.settable = False
    coordinator.async_update_listeners()

    entity = hass.data[CLIMATE_DOMAIN].get_entity(entity_id)
    assert entity is not None
    assert entity.preset_modes == [PRESET_NONE]


async def test_climate_does_not_advertise_read_only_fan_control(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Do not advertise fan control when all fan characteristics are read-only."""
    (
        entity_id,
        _,
        management_point,
        coordinator,
    ) = await _async_setup_climate_service_fixture(hass, config_entry, entity_registry)
    climate_control = management_point.climate_control
    assert climate_control is not None
    fan_operation = climate_control.fan_operation()
    assert fan_operation is not None and fan_operation.fan_speed is not None
    fan_operation.fan_speed.current_mode.settable = False
    fan_operation.fan_speed.current_mode.value = FANMODE_FIXED
    fixed = fan_operation.fan_speed.modes[FANMODE_FIXED]
    fixed.settable = False
    fixed.value = 3
    coordinator.async_update_listeners()

    entity = hass.data[CLIMATE_DOMAIN].get_entity(entity_id)
    assert entity is not None
    assert entity.fan_modes
    assert not entity.supported_features & ClimateEntityFeature.FAN_MODE


async def test_climate_rejects_disabling_read_only_active_preset(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Reject changing presets when an active preset is read-only."""
    (
        entity_id,
        _,
        management_point,
        coordinator,
    ) = await _async_setup_climate_service_fixture(hass, config_entry, entity_registry)
    climate_control = management_point.climate_control
    assert climate_control is not None
    assert climate_control.on_off_mode is not None
    holiday_mode = climate_control.mode_characteristic("holidayMode")
    assert holiday_mode is not None
    climate_control.on_off_mode.value = "on"
    holiday_mode.value.enabled = True
    holiday_mode.settable = False
    coordinator.async_update_listeners()
    entity = hass.data[CLIMATE_DOMAIN].get_entity(entity_id)
    assert entity is not None
    assert entity.preset_mode == PRESET_AWAY
    assert entity.preset_mode in entity.preset_modes

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: entity_id, "preset_mode": PRESET_NONE},
            blocking=True,
        )

    assert err.value.translation_key == "preset_mode_unavailable"
    mock_onecta_client.put_management_point.assert_not_awaited()
    mock_onecta_client.patch_characteristic.assert_not_awaited()


async def test_climate_state_reports_enabled_away_preset(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Expose away when the cloud model reports holiday mode enabled."""
    (
        entity_id,
        _,
        management_point,
        coordinator,
    ) = await _async_setup_climate_service_fixture(hass, config_entry, entity_registry)
    climate_control = management_point.climate_control
    assert climate_control is not None
    holiday_mode = climate_control.mode_characteristic("holidayMode")
    assert holiday_mode is not None
    holiday_mode.value.enabled = True
    coordinator.async_update_listeners()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[ClimateEntityStateAttribute.PRESET_MODE] == PRESET_AWAY


async def test_climate_service_publishes_preset_disable_before_replacement_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Publish a successful disable when enabling the replacement fails."""
    (
        entity_id,
        gateway_id,
        management_point,
        coordinator,
    ) = await _async_setup_climate_service_fixture(hass, config_entry, entity_registry)
    climate_control = management_point.climate_control
    assert climate_control is not None
    assert climate_control.on_off_mode is not None
    climate_control.on_off_mode.value = "on"
    powerful_mode = climate_control.mode_characteristic("powerfulMode")
    assert powerful_mode is not None
    powerful_mode.value = "on"
    coordinator.async_update_listeners()
    mock_onecta_client.post_management_point.side_effect = OnectaConnectionError(
        "test connection failure", method="POST", path="/test"
    )

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: entity_id, "preset_mode": PRESET_AWAY},
            blocking=True,
        )

    assert err.value.translation_key == "set_preset_mode_failed"
    assert powerful_mode.value == "off"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[ClimateEntityStateAttribute.PRESET_MODE] == PRESET_NONE
    mock_onecta_client.patch_characteristic.assert_awaited_once_with(
        gateway_id,
        management_point.embedded_id,
        "powerfulMode",
        "off",
        path=None,
    )
    mock_onecta_client.post_management_point.assert_awaited_once()


async def test_climate_service_updates_entity_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Publish the updated temperature after a successful climate service call."""
    (
        entity_id,
        gateway_id,
        point,
        _coordinator,
    ) = await _async_setup_climate_service_fixture(hass, config_entry, entity_registry)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ClimateServiceArgument.TEMPERATURE: 22},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[ClimateEntityStateAttribute.TARGET_TEMPERATURE] == 22

    mock_onecta_client.patch_characteristic.assert_awaited_once_with(
        gateway_id,
        point.embedded_id,
        "temperatureControl",
        22,
        path="/operationModes/heating/setpoints/roomTemperature",
    )


async def test_climate_service_failure_preserves_entity_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Keep the previous temperature when Daikin rejects a climate write."""
    (
        entity_id,
        gateway_id,
        point,
        _coordinator,
    ) = await _async_setup_climate_service_fixture(hass, config_entry, entity_registry)
    state_before = hass.states.get(entity_id)
    assert state_before is not None
    mock_onecta_client.patch_characteristic.side_effect = OnectaConnectionError(
        "test connection failure", method="PATCH", path="/test"
    )

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: entity_id, ClimateServiceArgument.TEMPERATURE: 22},
            blocking=True,
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "set_temperature_failed"
    state = hass.states.get(entity_id)
    assert state == state_before
    mock_onecta_client.patch_characteristic.assert_awaited_once_with(
        gateway_id,
        point.embedded_id,
        "temperatureControl",
        22,
        path="/operationModes/heating/setpoints/roomTemperature",
    )


async def test_climate_service_rejected_token_preserves_entity_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Translate rejected credentials when a climate action reaches Daikin."""
    await _async_setup_fixture(hass, config_entry, "climate_fixedfanmode")
    coordinator = config_entry.runtime_data
    gateway_id = next(iter(coordinator.data))
    aioclient_mock.patch(
        "https://api.onecta.daikineurope.com/v1/gateway-devices/"
        f"{gateway_id}/management-points/climateControl/characteristics/"
        "temperatureControl",
        status=401,
        text="Unauthorized",
    )
    entity_id = hass.states.async_entity_ids(CLIMATE_DOMAIN)[0]
    state_before = hass.states.get(entity_id)
    assert state_before is not None
    temperature_before = state_before.attributes[
        ClimateEntityStateAttribute.TARGET_TEMPERATURE
    ]

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: entity_id, ClimateServiceArgument.TEMPERATURE: 22},
            blocking=True,
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "set_temperature_failed"
    state_after = hass.states.get(entity_id)
    assert state_after is not None
    assert (
        state_after.attributes[ClimateEntityStateAttribute.TARGET_TEMPERATURE]
        == temperature_before
    )
    assert len(aioclient_mock.mock_calls) == 1
    assert str(aioclient_mock.mock_calls[0][1]) == (
        "https://api.onecta.daikineurope.com/v1/gateway-devices/"
        f"{gateway_id}/management-points/climateControl/characteristics/"
        "temperatureControl"
    )


async def test_climate_service_oauth_connection_error_is_translated(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Translate token-endpoint connectivity errors into climate action errors."""
    await _async_setup_fixture(hass, config_entry, "climate_fixedfanmode")
    mock_onecta_client.patch_characteristic.side_effect = (
        OAuth2TokenRequestConnectionError(domain=DOMAIN)
    )
    entity_id = hass.states.async_entity_ids(CLIMATE_DOMAIN)[0]
    state_before = hass.states.get(entity_id)
    assert state_before is not None

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: entity_id, ClimateServiceArgument.TEMPERATURE: 22},
            blocking=True,
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "set_temperature_failed"
    assert hass.states.get(entity_id) == state_before


@pytest.mark.parametrize(
    (
        "service",
        "service_data",
        "initial_power",
        "expected_state",
        "power_command",
        "key",
    ),
    [
        (SERVICE_TURN_ON, {}, "off", HVACMode.OFF, "on", "turn_on_failed"),
        (SERVICE_TURN_OFF, {}, "on", HVACMode.HEAT, "off", "turn_off_failed"),
        (
            SERVICE_SET_HVAC_MODE,
            {"hvac_mode": HVACMode.OFF},
            "on",
            HVACMode.HEAT,
            "off",
            "set_hvac_mode_failed",
        ),
    ],
)
async def test_climate_service_preserves_power_state_when_command_fails(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
    service: str,
    service_data: dict[str, HVACMode],
    initial_power: str,
    expected_state: HVACMode,
    power_command: str,
    key: str,
) -> None:
    """Keep the published power state when a service command is rejected."""
    (
        entity_id,
        gateway_id,
        management_point,
        coordinator,
    ) = await _async_setup_climate_service_fixture(hass, config_entry, entity_registry)
    assert management_point.climate_control is not None
    climate_control = management_point.climate_control
    assert climate_control.on_off_mode is not None
    climate_control.on_off_mode.value = initial_power
    climate_control.operation_mode.value = "heating"
    coordinator.async_update_listeners()
    mock_onecta_client.patch_characteristic.side_effect = OnectaConnectionError(
        "test connection failure", method="PATCH", path="/test"
    )

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id, **service_data},
            blocking=True,
        )

    assert err.value.translation_key == key
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state
    mock_onecta_client.patch_characteristic.assert_awaited_once_with(
        gateway_id,
        management_point.embedded_id,
        "onOffMode",
        power_command,
        path=None,
    )


@pytest.mark.parametrize(
    ("service", "service_data", "initial_power"),
    [
        (SERVICE_TURN_ON, {}, "on"),
        (SERVICE_TURN_OFF, {}, "off"),
        (SERVICE_SET_HVAC_MODE, {"hvac_mode": HVACMode.HEAT}, "on"),
    ],
)
async def test_climate_service_skips_matching_power_command(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
    service: str,
    service_data: dict[str, HVACMode],
    initial_power: str,
) -> None:
    """Avoid cloud calls when the requested power or HVAC mode is already active."""
    (
        entity_id,
        _,
        management_point,
        coordinator,
    ) = await _async_setup_climate_service_fixture(hass, config_entry, entity_registry)
    assert management_point.climate_control is not None
    management_point.climate_control.on_off_mode.value = initial_power
    management_point.climate_control.operation_mode.value = "heating"
    coordinator.async_update_listeners()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id, **service_data},
        blocking=True,
    )

    mock_onecta_client.patch_characteristic.assert_not_awaited()


@pytest.mark.parametrize(
    ("native_mode", "hvac_mode"),
    [("heatingDay", HVACMode.HEAT), ("auto", HVACMode.HEAT_COOL)],
)
async def test_climate_service_keeps_matching_native_hvac_mode(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
    native_mode: str,
    hvac_mode: HVACMode,
) -> None:
    """Keep a native mode when it already maps to the requested HA mode."""
    (
        entity_id,
        _,
        management_point,
        coordinator,
    ) = await _async_setup_climate_service_fixture(hass, config_entry, entity_registry)
    assert management_point.climate_control is not None
    operation_mode = management_point.climate_control.operation_mode
    assert operation_mode is not None
    operation_mode.value = native_mode
    operation_mode.values = [native_mode]
    on_off_mode = management_point.climate_control.on_off_mode
    assert on_off_mode is not None
    on_off_mode.value = "on"
    coordinator.async_update_listeners()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: entity_id, "hvac_mode": hvac_mode},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == hvac_mode
    mock_onecta_client.patch_characteristic.assert_not_awaited()


async def test_climate_service_does_not_enable_boost_when_turn_on_fails(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Do not enable boost when its prerequisite turn-on command fails."""
    (
        entity_id,
        gateway_id,
        management_point,
        coordinator,
    ) = await _async_setup_climate_service_fixture(hass, config_entry, entity_registry)
    assert management_point.climate_control is not None
    climate_control = management_point.climate_control
    assert climate_control.on_off_mode is not None
    climate_control.on_off_mode.value = "off"
    powerful_mode = climate_control.mode_characteristic("powerfulMode")
    assert powerful_mode is not None
    powerful_mode.value = "off"
    coordinator.async_update_listeners()
    mock_onecta_client.patch_characteristic.side_effect = OnectaConnectionError(
        "test connection failure", method="PATCH", path="/test"
    )

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {ATTR_ENTITY_ID: entity_id, "preset_mode": PRESET_BOOST},
            blocking=True,
        )

    assert err.value.translation_key == "turn_on_failed"
    mock_onecta_client.patch_characteristic.assert_awaited_once_with(
        gateway_id,
        management_point.embedded_id,
        "onOffMode",
        "on",
        path=None,
    )
    assert powerful_mode.value == "off"


@pytest.mark.parametrize(
    ("service", "service_data", "initial_power"),
    [
        (SERVICE_TURN_ON, {}, "off"),
        (SERVICE_TURN_OFF, {}, "on"),
    ],
)
@pytest.mark.parametrize(
    "invalidate_power",
    [
        pytest.param(lambda point: setattr(point, "on_off_mode", None), id="removed"),
        pytest.param(
            lambda point: setattr(point.on_off_mode, "value", None),
            id="omitted",
        ),
        pytest.param(
            lambda point: setattr(point.on_off_mode, "value", "unknown"),
            id="invalid",
        ),
        pytest.param(
            lambda point: setattr(point.on_off_mode, "settable", False),
            id="read-only",
        ),
    ],
)
async def test_climate_service_rejects_unavailable_power(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    service: str,
    service_data: dict[str, HVACMode],
    initial_power: str,
    invalidate_power: Callable[[ManagementPoint], None],
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Reject unavailable power controls without sending a cloud command."""
    await _async_setup_fixture(hass, config_entry, "ururu")
    coordinator = config_entry.runtime_data
    assert coordinator.data is not None
    device = next(iter(coordinator.data.values()))
    point = device.management_point("climateControl")
    assert point is not None
    assert point.on_off_mode is not None
    point.on_off_mode.value = initial_power
    coordinator.async_update_listeners()
    invalidate_power(point)
    entity_id = entity_registry.async_get_entity_id(
        Platform.CLIMATE, DOMAIN, f"{device.id}_climateControl_roomTemperature"
    )
    assert entity_id is not None

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id, **service_data},
            blocking=True,
        )

    assert err.value.translation_key == "climate_power_unavailable"
    mock_onecta_client.patch_characteristic.assert_not_awaited()


async def test_climate_service_rejects_read_only_power_when_turning_off(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Reject turning off when the power characteristic is read-only."""
    await _async_setup_fixture(hass, config_entry, "ururu")
    coordinator = config_entry.runtime_data
    assert coordinator.data is not None
    device = next(iter(coordinator.data.values()))
    point = device.management_point("climateControl")
    assert point is not None
    assert point.on_off_mode is not None
    point.on_off_mode.value = "on"
    point.on_off_mode.settable = False
    assert point.operation_mode is not None
    point.operation_mode.values = [*(point.operation_mode.values or []), "off"]
    coordinator.async_update_listeners()
    entity_id = entity_registry.async_get_entity_id(
        Platform.CLIMATE, DOMAIN, f"{device.id}_climateControl_roomTemperature"
    )
    assert entity_id is not None

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: entity_id, "hvac_mode": HVACMode.OFF},
            blocking=True,
        )

    assert err.value.translation_key == "climate_power_unavailable"
    mock_onecta_client.patch_characteristic.assert_not_awaited()


@pytest.mark.parametrize(
    ("fixture", "setpoint_unit", "sensory_unit", "expected_unit"),
    [
        (
            "climate_fixedfanmode",
            "°F",
            "°F",
            UnitOfTemperature.FAHRENHEIT,
        ),
        ("altherma", None, "°F", UnitOfTemperature.FAHRENHEIT),
        ("altherma", None, None, UnitOfTemperature.CELSIUS),
        ("climate_fixedfanmode", "°K", None, UnitOfTemperature.CELSIUS),
    ],
)
async def test_native_temperature_unit(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    fixture: str,
    setpoint_unit: str | None,
    sensory_unit: str | None,
    expected_unit: UnitOfTemperature,
) -> None:
    """Use the Daikin temperature unit when present, otherwise default to Celsius."""
    await _async_setup_fixture(hass, config_entry, fixture)
    climate_entry = next(
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if entry.domain == CLIMATE_DOMAIN
    )
    entity = hass.data[CLIMATE_DOMAIN].get_entity(climate_entry.entity_id)
    assert isinstance(entity, DaikinClimate)

    cc = entity._climate_control()
    assert cc is not None
    setpoint = entity._get_setpoint(cc)
    assert setpoint is not None
    setpoint.unit = setpoint_unit
    sensory_target = {
        "leavingWaterOffset": "leavingWaterTemperature",
    }.get(entity._setpoint, entity._setpoint)
    sensory_data = cc.sensory_data(sensory_target)
    assert sensory_data is not None
    sensory_data.unit = sensory_unit
    config_entry.runtime_data.async_update_listeners()

    assert entity.native_temperature_unit == expected_unit


@pytest.mark.parametrize(
    ("configure_control", "service", "service_data", "translation_key"),
    [
        pytest.param(
            _make_vertical_swing_read_only,
            SERVICE_SET_SWING_MODE,
            {"swing_mode": SWING_OFF},
            "swing_control_unavailable",
            id="vertical-swing-read-only",
        ),
        pytest.param(
            _make_horizontal_swing_read_only,
            SERVICE_SET_SWING_HORIZONTAL_MODE,
            {"swing_horizontal_mode": SWING_OFF},
            "swing_control_unavailable",
            id="horizontal-swing-read-only",
        ),
        pytest.param(
            _make_powerful_mode_read_only,
            SERVICE_SET_PRESET_MODE,
            {"preset_mode": PRESET_BOOST},
            "preset_mode_unavailable",
            id="boost-read-only",
        ),
    ],
)
async def test_climate_platform_services_and_management_points(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_onecta_client: MockOnectaClient,
    configure_control: Callable[[ManagementPoint], None],
    service: str,
    service_data: dict[str, str],
    translation_key: str,
) -> None:
    """Test platform services with real entities for two management points."""
    gateway_devices = _load_gateway_devices("altherma")
    gateway = next(
        device for device in gateway_devices if device.id.endswith("000000000107")
    )
    bedroom_gateway = next(
        device for device in gateway_devices if device.id.endswith("000000000111")
    )
    living_room_control = gateway.management_point("climateControl")
    bedroom_control = bedroom_gateway.management_point("climateControl")
    assert living_room_control is not None
    assert bedroom_control is not None
    living_room_control.embedded_id = "living_room"
    living_room_control.name.value = "Living Room"
    bedroom_control = deepcopy(bedroom_control)
    bedroom_control.embedded_id = "bedroom"
    bedroom_control.name = None
    gateway.management_points.append(bedroom_control)
    gateway.id = "gateway"

    climate_controls = {
        "living_room": living_room_control,
        "bedroom": bedroom_control,
    }
    for control, temperature in ((living_room_control, 20), (bedroom_control, 18)):
        assert control.operation_mode is not None
        control.operation_mode.value = "heating"
        control.operation_mode.values = ["heating", "cooling"]
        assert control.on_off_mode is not None
        control.on_off_mode.value = "on"
        assert control.climate_control is not None
        setpoint = control.climate_control.setpoint("roomTemperature", "heating")
        assert setpoint is not None
        setpoint.value = temperature
        for preset in ("econoMode", "powerfulMode"):
            characteristic = control.characteristic(preset)
            assert characteristic is not None
            characteristic.value = "off"

    await _async_setup_fixture(
        hass, config_entry, "altherma", gateway_devices=[gateway]
    )

    living_room_entity_id = entity_registry.async_get_entity_id(
        Platform.CLIMATE, DOMAIN, "gateway_living_room_roomTemperature"
    )
    bedroom_entity_id = entity_registry.async_get_entity_id(
        Platform.CLIMATE, DOMAIN, "gateway_bedroom_roomTemperature"
    )
    assert living_room_entity_id is not None
    assert bedroom_entity_id is not None
    living_room_device = device_registry.async_get_child_device_by_identifier(
        (DOMAIN, "gateway_living_room"), config_entry.entry_id
    )
    bedroom_device = device_registry.async_get_child_device_by_identifier(
        (DOMAIN, "gateway_bedroom"), config_entry.entry_id
    )
    assert living_room_device is not None
    assert bedroom_device is not None
    gateway_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "gateway"), config_entry.entry_id
    )
    assert gateway_device is not None
    assert living_room_device.name == "Living Room"
    assert bedroom_device.name == "Climate zone"
    for embedded_id, zone_device in (
        ("living_room", living_room_device),
        ("bedroom", bedroom_device),
    ):
        binary_sensor_id = entity_registry.async_get_entity_id(
            Platform.BINARY_SENSOR,
            DOMAIN,
            f"gateway_{embedded_id}_isInErrorState",
        )
        assert binary_sensor_id is not None
        binary_sensor_entry = entity_registry.async_get(binary_sensor_id)
        assert binary_sensor_entry is not None
        assert binary_sensor_entry.device_id == zone_device.id

    async def call_service(service: str, **service_data: str | int | HVACMode) -> None:
        """Call a climate service for the living room entity."""
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            service,
            {ATTR_ENTITY_ID: living_room_entity_id, **service_data},
            blocking=True,
        )

    await call_service(SERVICE_SET_TEMPERATURE, temperature=21)
    await call_service(SERVICE_SET_HVAC_MODE, hvac_mode=HVACMode.COOL)
    await call_service(SERVICE_SET_HVAC_MODE, hvac_mode=HVACMode.COOL)
    await call_service(SERVICE_SET_TEMPERATURE, temperature=21)
    await call_service(SERVICE_SET_FAN_MODE, fan_mode="quiet")
    await call_service(SERVICE_SET_SWING_MODE, swing_mode=SWING_ON)
    await call_service(SERVICE_SET_SWING_MODE, swing_mode=SWING_ON)
    await call_service(
        SERVICE_SET_SWING_HORIZONTAL_MODE, swing_horizontal_mode=SWING_ON
    )
    await call_service(
        SERVICE_SET_SWING_HORIZONTAL_MODE, swing_horizontal_mode=SWING_ON
    )
    await call_service(SERVICE_SET_PRESET_MODE, preset_mode=PRESET_ECO)
    await call_service(SERVICE_SET_PRESET_MODE, preset_mode=PRESET_ECO)
    await call_service(SERVICE_TURN_OFF)
    await call_service(SERVICE_TURN_OFF)

    living_room_state = hass.states.get(living_room_entity_id)
    assert living_room_state is not None
    assert living_room_state.state == HVACMode.OFF

    await call_service(SERVICE_TURN_ON)
    await call_service(SERVICE_TURN_ON)

    living_room_state = hass.states.get(living_room_entity_id)
    bedroom_state = hass.states.get(bedroom_entity_id)
    assert living_room_state is not None
    assert bedroom_state is not None
    assert living_room_state.state == HVACMode.COOL
    assert mock_onecta_client.patch_characteristic.await_args_list == [
        call(
            "gateway",
            "living_room",
            "temperatureControl",
            21,
            path="/operationModes/heating/setpoints/roomTemperature",
        ),
        call("gateway", "living_room", "operationMode", "cooling", path=None),
        call(
            "gateway",
            "living_room",
            "temperatureControl",
            21,
            path="/operationModes/cooling/setpoints/roomTemperature",
        ),
        call(
            "gateway",
            "living_room",
            "fanControl",
            "quiet",
            path="/operationModes/cooling/fanSpeed/currentMode",
        ),
        call(
            "gateway",
            "living_room",
            "fanControl",
            "swing",
            path="/operationModes/cooling/fanDirection/vertical/currentMode",
        ),
        call(
            "gateway",
            "living_room",
            "fanControl",
            "swing",
            path="/operationModes/cooling/fanDirection/horizontal/currentMode",
        ),
        call("gateway", "living_room", "econoMode", "on", path=None),
        call("gateway", "living_room", "onOffMode", "off", path=None),
        call("gateway", "living_room", "onOffMode", "on", path=None),
    ]
    assert living_room_state.attributes[ClimateEntityStateAttribute.FAN_MODE] == "quiet"
    assert (
        living_room_state.attributes[ClimateEntityStateAttribute.SWING_MODE] == SWING_ON
    )
    assert (
        living_room_state.attributes[ClimateEntityStateAttribute.SWING_HORIZONTAL_MODE]
        == SWING_ON
    )
    assert (
        living_room_state.attributes[ClimateEntityStateAttribute.PRESET_MODE]
        == PRESET_ECO
    )
    assert bedroom_state.state == HVACMode.HEAT
    assert (
        bedroom_state.attributes[ClimateEntityStateAttribute.TARGET_TEMPERATURE] == 18
    )

    mock_onecta_client.patch_characteristic.reset_mock()

    configure_control(climate_controls["living_room"])
    with pytest.raises(ServiceValidationError) as err:
        await call_service(service, **service_data)
    assert err.value.translation_key == translation_key

    assert climate_controls["living_room"].climate_control is not None
    setpoint = climate_controls["living_room"].climate_control.setpoint(
        "roomTemperature"
    )
    assert setpoint is not None
    setpoint.settable = False
    current_state = hass.states.get(living_room_entity_id)
    assert current_state is not None
    with pytest.raises(ServiceValidationError) as err:
        await call_service(
            SERVICE_SET_TEMPERATURE,
            temperature=current_state.attributes[
                ClimateEntityStateAttribute.TARGET_TEMPERATURE
            ],
        )
    assert err.value.translation_key == "climate_temperature_unavailable"
    with pytest.raises(ServiceValidationError) as err:
        await call_service(SERVICE_SET_TEMPERATURE, temperature=22)
    assert err.value.translation_key == "climate_temperature_unavailable"

    with pytest.raises(ServiceValidationError):
        await call_service(
            SERVICE_SET_TEMPERATURE,
            hvac_mode=HVACMode.HEAT_COOL,
            temperature=22,
        )

    with pytest.raises(ServiceValidationError):
        await call_service(SERVICE_SET_SWING_MODE, swing_mode="unsupported")

    climate_controls["living_room"].operation_mode.settable = False
    with pytest.raises(ServiceValidationError) as err:
        await call_service(SERVICE_SET_HVAC_MODE, hvac_mode=HVACMode.HEAT)
    assert err.value.translation_key == "climate_hvac_mode_unavailable"

    climate_controls["living_room"].operation_mode = None
    with pytest.raises(ServiceValidationError) as err:
        await call_service(SERVICE_SET_TEMPERATURE, temperature=22)
    assert err.value.translation_key == "climate_operation_mode_unavailable"

    with pytest.raises(ServiceValidationError):
        await call_service(SERVICE_SET_HVAC_MODE, hvac_mode=HVACMode.HEAT)

    mock_onecta_client.patch_characteristic.assert_not_awaited()

    climate_controls["living_room"].operation_mode = Characteristic(
        value="cooling", values=["heating", "cooling"], settable=True
    )
    setpoint.settable = True

    mock_onecta_client.patch_characteristic.side_effect = OnectaConnectionError(
        "test connection failure", method="PATCH", path="/test"
    )
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: bedroom_entity_id, "temperature": 22},
            blocking=True,
        )
    assert err.value.translation_placeholders == {
        "device": f"{gateway_device.name} Climate zone"
    }

    device_registry.async_update_child_device(
        living_room_device.id, name_by_user="Renamed living room"
    )
    mock_onecta_client.patch_characteristic.side_effect = OnectaConnectionError(
        "test connection failure", method="PATCH", path="/test"
    )
    with pytest.raises(HomeAssistantError) as err:
        await call_service(SERVICE_SET_TEMPERATURE, temperature=22)
    assert err.value.translation_key == "set_temperature_failed"
    assert err.value.translation_placeholders == {"device": "Renamed living room"}


@pytest.mark.parametrize(
    (
        "unit_system",
        "service_temperature",
        "step_value",
        "initial_temperature",
        "expected_temperature",
        "should_write",
    ),
    [
        pytest.param(
            US_CUSTOMARY_SYSTEM, 76, 0.5, 20, 24.5, True, id="fahrenheit-conversion"
        ),
        pytest.param(METRIC_SYSTEM, 24.4, 1, 20, 24, True, id="whole-step-rounding"),
        pytest.param(
            METRIC_SYSTEM, 20.1, 0.1, 20, 20.1, True, id="decimal-step-rounding"
        ),
        pytest.param(METRIC_SYSTEM, 24.4, None, 20, 24.5, True, id="default-step"),
        pytest.param(METRIC_SYSTEM, 10.4, 3, 20, 10, True, id="clamp-to-minimum"),
        pytest.param(
            US_CUSTOMARY_SYSTEM,
            76,
            0.5,
            24.5,
            24.5,
            False,
            id="rounded-value-is-current-target",
        ),
    ],
)
async def test_climate_temperature_rounds_to_native_step(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
    unit_system: UnitSystem,
    service_temperature: float,
    step_value: float | None,
    initial_temperature: float,
    expected_temperature: float,
    should_write: bool,
) -> None:
    """Convert, round, and clamp service targets before writing to Daikin."""
    hass.config.units = unit_system
    (
        entity_id,
        gateway_id,
        point,
        coordinator,
    ) = await _async_setup_climate_service_fixture(hass, config_entry, entity_registry)
    assert point.climate_control is not None
    setpoint = point.climate_control.setpoint("roomTemperature", "heating")
    assert setpoint is not None
    setpoint.step_value = step_value
    setpoint.value = initial_temperature
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    mock_onecta_client.patch_characteristic.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, "temperature": service_temperature},
        blocking=True,
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, "temperature": service_temperature},
        blocking=True,
    )

    assert setpoint.value == expected_temperature
    expected_calls = {
        True: [
            call(
                gateway_id,
                point.embedded_id,
                "temperatureControl",
                expected_temperature,
                path="/operationModes/heating/setpoints/roomTemperature",
            )
        ],
        False: [],
    }
    assert (
        mock_onecta_client.patch_characteristic.await_args_list
        == expected_calls[should_write]
    )


async def test_climate_temperature_rounding_is_anchored_to_minimum(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Round relative to a nonzero, non-step-aligned setpoint minimum."""
    (
        entity_id,
        gateway_id,
        point,
        coordinator,
    ) = await _async_setup_climate_service_fixture(hass, config_entry, entity_registry)
    assert point.climate_control is not None
    setpoint = point.climate_control.setpoint("roomTemperature", "heating")
    assert setpoint is not None
    setpoint.min_value = 17.2
    setpoint.step_value = 0.5
    setpoint.value = 20
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    mock_onecta_client.patch_characteristic.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, "temperature": 18},
        blocking=True,
    )

    assert setpoint.value == 18.2
    mock_onecta_client.patch_characteristic.assert_awaited_once_with(
        gateway_id,
        point.embedded_id,
        "temperatureControl",
        18.2,
        path="/operationModes/heating/setpoints/roomTemperature",
    )


async def test_climate_set_temperature_with_off_writes_target_before_power_off(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Apply a target temperature before powering the unit off."""
    (
        entity_id,
        gateway_id,
        point,
        coordinator,
    ) = await _async_setup_climate_service_fixture(hass, config_entry, entity_registry)
    assert point.climate_control is not None
    assert point.climate_control.on_off_mode is not None
    point.climate_control.on_off_mode.value = "on"
    setpoint = point.climate_control.setpoint("roomTemperature", "heating")
    assert setpoint is not None
    setpoint.value = 20
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    mock_onecta_client.patch_characteristic.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: entity_id,
            ClimateServiceArgument.HVAC_MODE: HVACMode.OFF,
            ClimateServiceArgument.TEMPERATURE: 22,
        },
        blocking=True,
    )

    assert mock_onecta_client.patch_characteristic.await_args_list == [
        call(
            gateway_id,
            point.embedded_id,
            "temperatureControl",
            22,
            path="/operationModes/heating/setpoints/roomTemperature",
        ),
        call(gateway_id, point.embedded_id, "onOffMode", "off", path=None),
    ]


async def test_climate_negative_half_step_rounds_away_from_zero(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Round negative half-step targets away from zero with a native minimum."""
    (
        entity_id,
        gateway_id,
        point,
        coordinator,
    ) = await _async_setup_climate_service_fixture(hass, config_entry, entity_registry)
    assert point.climate_control is not None
    setpoint = point.climate_control.setpoint("roomTemperature", "heating")
    assert setpoint is not None
    setpoint.min_value = -10
    setpoint.step_value = 1
    setpoint.value = -4
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    mock_onecta_client.patch_characteristic.reset_mock()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, "temperature": -2.5},
        blocking=True,
    )

    assert setpoint.value == -3
    mock_onecta_client.patch_characteristic.assert_awaited_once_with(
        gateway_id,
        point.embedded_id,
        "temperatureControl",
        -3,
        path="/operationModes/heating/setpoints/roomTemperature",
    )


async def test_humidification_is_not_reported_as_dry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Keep unsupported humidification distinct from the native dry mode."""
    await _async_setup_fixture(hass, config_entry, "ururu")
    coordinator = config_entry.runtime_data
    assert coordinator.data is not None
    device = next(iter(coordinator.data.values()))
    point = next(iter(device.device.management_points_by_type("climateControl")))
    assert point.climate_control is not None
    assert point.climate_control.operation_mode is not None
    point.climate_control.operation_mode.value = "humidification"
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    climate_entry = next(
        entry
        for entry in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if entry.domain == CLIMATE_DOMAIN
    )
    state = hass.states.get(climate_entry.entity_id)
    assert state is not None
    assert state.state == "unknown"


@pytest.mark.parametrize(
    ("gateway_id", "native_mode", "expected_mode"),
    [
        ("test-gateway-1", "floorHeatingAirflow", "floorheatingairflow"),
        ("test-gateway-2", "windNice", "windnice"),
    ],
)
async def test_climate_state_translates_daikin_swing_modes(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    gateway_id: str,
    native_mode: str,
    expected_mode: str,
) -> None:
    """Expose Daikin-specific swing values through the created climate entity."""
    await _async_setup_fixture(hass, config_entry, "climate_floorheatingairflow")
    coordinator = config_entry.runtime_data
    device = coordinator.data[gateway_id]
    management_point = device.management_point("climateControl")
    assert management_point is not None
    climate_control = management_point.climate_control
    assert climate_control is not None
    fan_operation = climate_control.fan_operation()
    assert fan_operation is not None and fan_operation.fan_direction is not None
    assert fan_operation.fan_direction.vertical is not None
    fan_operation.fan_direction.vertical.current_mode.value = native_mode
    coordinator.async_update_listeners()

    entity_id = entity_registry.async_get_entity_id(
        Platform.CLIMATE, DOMAIN, f"{gateway_id}_climateControl_roomTemperature"
    )
    assert entity_id is not None
    entity = hass.data[CLIMATE_DOMAIN].get_entity(entity_id)
    assert isinstance(entity, DaikinClimate)
    assert entity.swing_mode == expected_mode
    assert expected_mode in entity.swing_modes


async def test_climate_state_keeps_fixed_swing_distinct_from_off(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Keep Daikin's fixed swing direction distinct from swing off in HA."""
    await _async_setup_fixture(hass, config_entry, "climate_fixedfanmode")
    coordinator = config_entry.runtime_data
    gateway_id, device = next(iter(coordinator.data.items()))
    management_point = device.management_point("climateControl")
    assert management_point is not None
    climate_control = management_point.climate_control
    assert climate_control is not None
    fan_operation = climate_control.fan_operation("heating")
    assert fan_operation is not None and fan_operation.fan_direction is not None
    assert fan_operation.fan_direction.vertical is not None
    current_mode = fan_operation.fan_direction.vertical.current_mode
    current_mode.value = "fixed"
    assert current_mode.values is not None
    current_mode.values.append("fixed")
    coordinator.async_update_listeners()

    entity_id = entity_registry.async_get_entity_id(
        Platform.CLIMATE, DOMAIN, f"{gateway_id}_climateControl_roomTemperature"
    )
    assert entity_id is not None
    entity = hass.data[CLIMATE_DOMAIN].get_entity(entity_id)
    assert isinstance(entity, DaikinClimate)
    assert entity.swing_mode == "fixed"
    assert "fixed" in entity.swing_modes
    assert entity.swing_mode != SWING_OFF


@pytest.mark.parametrize(
    ("fixed_settable", "fixed_value", "expected_swing_mode"),
    [
        pytest.param(False, 2, "fixed", id="fixed-control-read-only"),
        pytest.param(True, 9, None, id="position-outside-supported-range"),
    ],
)
async def test_climate_swing_state_is_in_advertised_modes(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    fixed_settable: bool,
    fixed_value: int,
    expected_swing_mode: str | None,
) -> None:
    """Never report a fixed swing position outside the advertised modes."""
    await _async_setup_fixture(hass, config_entry, "dry")
    coordinator = config_entry.runtime_data
    gateway_id = DRY_FIXED_DIRECTION_GATEWAY_ID
    device = coordinator.data[gateway_id]
    point = device.management_point("climateControl")
    assert point is not None and point.climate_control is not None
    fan_operation = point.climate_control.fan_operation()
    assert fan_operation is not None and fan_operation.fan_direction is not None
    vertical = fan_operation.fan_direction.vertical
    assert vertical is not None
    vertical.current_mode.value = "fixed"
    vertical.current_mode.settable = True
    vertical.current_mode.values = ["swing", "fixed"]
    fixed = vertical.modes[FANMODE_FIXED]
    fixed.settable = fixed_settable
    fixed.value = fixed_value
    fixed.min_value = 1
    fixed.max_value = 5
    fixed.step_value = 1
    coordinator.async_update_listeners()

    entity_id = entity_registry.async_get_entity_id(
        Platform.CLIMATE, DOMAIN, f"{gateway_id}_climateControl_roomTemperature"
    )
    assert entity_id is not None
    entity = hass.data[CLIMATE_DOMAIN].get_entity(entity_id)
    assert isinstance(entity, DaikinClimate)
    assert entity.swing_mode == expected_swing_mode
    assert expected_swing_mode is None or expected_swing_mode in entity.swing_modes


def _vertical_fixed_swing_axis(direction: FanDirection) -> FanDirectionAxis:
    """Return the fixture's vertical fixed-position axis."""
    axis = direction.vertical
    assert axis is not None
    assert axis.modes is not None
    assert axis.current_mode.values is not None
    axis.current_mode.values.insert(1, "stop")
    assert (
        axis.modes[FANMODE_FIXED].min_value,
        axis.modes[FANMODE_FIXED].max_value,
    ) == (
        1,
        5,
    )
    return axis


def _horizontal_fixed_swing_axis(direction: FanDirection) -> FanDirectionAxis:
    """Return a horizontal axis with the fixture's fixed-position metadata."""
    vertical = direction.vertical
    assert vertical is not None
    axis = deepcopy(vertical)
    assert axis.modes is not None
    assert axis.current_mode.values is not None
    axis.modes[FANMODE_FIXED].value = 7
    axis.modes[FANMODE_FIXED].max_value = 7
    direction.horizontal = axis
    return axis


@pytest.mark.parametrize(
    (
        "configure_axis",
        "direction",
        "service",
        "argument",
        "state_attribute",
        "capability_attribute",
        "initial_position",
        "target_position",
        "swing_modes",
    ),
    [
        pytest.param(
            _vertical_fixed_swing_axis,
            "vertical",
            SERVICE_SET_SWING_MODE,
            "swing_mode",
            ClimateEntityStateAttribute.SWING_MODE,
            ClimateEntityCapabilityAttribute.SWING_MODES,
            2,
            3,
            [SWING_ON, SWING_OFF, "1", "2", "3", "4", "5"],
            id="vertical",
        ),
        pytest.param(
            _horizontal_fixed_swing_axis,
            "horizontal",
            SERVICE_SET_SWING_HORIZONTAL_MODE,
            "swing_horizontal_mode",
            ClimateEntityStateAttribute.SWING_HORIZONTAL_MODE,
            ClimateEntityCapabilityAttribute.SWING_HORIZONTAL_MODES,
            7,
            2,
            [SWING_ON, "1", "2", "3", "4", "5", "6", "7"],
            id="horizontal",
        ),
    ],
)
async def test_climate_service_sets_fixed_swing_position(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
    configure_axis: Callable[[FanDirection], FanDirectionAxis],
    direction: str,
    service: str,
    argument: str,
    state_attribute: ClimateEntityStateAttribute,
    capability_attribute: ClimateEntityCapabilityAttribute,
    initial_position: int,
    target_position: int,
    swing_modes: list[str],
) -> None:
    """Expose and set fixed louvre positions through both swing services."""
    await _async_setup_fixture(hass, config_entry, "dry")
    coordinator = config_entry.runtime_data
    device = coordinator.data[DRY_FIXED_DIRECTION_GATEWAY_ID]
    management_point = device.management_point("climateControl")
    assert management_point is not None
    climate_control = management_point.climate_control
    assert climate_control is not None
    fan_operation = climate_control.fan_operation()
    assert fan_operation is not None and fan_operation.fan_direction is not None
    axis = configure_axis(fan_operation.fan_direction)
    assert axis.modes is not None
    fixed = axis.modes[FANMODE_FIXED]
    assert fixed.value == initial_position

    entity_id = entity_registry.async_get_entity_id(
        Platform.CLIMATE,
        DOMAIN,
        f"{DRY_FIXED_DIRECTION_GATEWAY_ID}_climateControl_roomTemperature",
    )
    assert entity_id is not None
    coordinator.async_update_listeners()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[state_attribute] == str(initial_position)
    axis.current_mode.value = "swing"
    coordinator.async_update_listeners()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[state_attribute] == SWING_ON
    assert state.attributes[capability_attribute] == swing_modes

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id, argument: str(target_position)},
        blocking=True,
    )

    assert mock_onecta_client.patch_characteristic.await_args_list == [
        call(
            DRY_FIXED_DIRECTION_GATEWAY_ID,
            "climateControl",
            "fanControl",
            FANMODE_FIXED,
            path=f"/operationModes/dry/fanDirection/{direction}/currentMode",
        ),
        call(
            DRY_FIXED_DIRECTION_GATEWAY_ID,
            "climateControl",
            "fanControl",
            target_position,
            path=f"/operationModes/dry/fanDirection/{direction}/modes/fixed",
        ),
    ]
    assert axis.current_mode.value == FANMODE_FIXED
    assert fixed.value == target_position
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[state_attribute] == str(target_position)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id, argument: str(target_position)},
        blocking=True,
    )
    assert mock_onecta_client.patch_characteristic.await_count == 2


async def test_climate_service_publishes_fixed_mode_when_position_write_fails(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Publish the fixed mode if its following louvre-position write fails."""
    await _async_setup_fixture(hass, config_entry, "dry")
    coordinator = config_entry.runtime_data
    device = coordinator.data[DRY_FIXED_DIRECTION_GATEWAY_ID]
    management_point = device.management_point("climateControl")
    assert management_point is not None
    climate_control = management_point.climate_control
    assert climate_control is not None
    fan_operation = climate_control.fan_operation()
    assert fan_operation is not None and fan_operation.fan_direction is not None
    vertical = fan_operation.fan_direction.vertical
    assert vertical is not None
    assert vertical.current_mode.values is not None
    vertical.current_mode.values.insert(1, "stop")
    vertical.current_mode.value = "swing"
    coordinator.async_update_listeners()

    entity_id = entity_registry.async_get_entity_id(
        Platform.CLIMATE,
        DOMAIN,
        f"{DRY_FIXED_DIRECTION_GATEWAY_ID}_climateControl_roomTemperature",
    )
    assert entity_id is not None
    mock_onecta_client.patch_characteristic.side_effect = [
        None,
        OnectaConnectionError("test connection failure", method="PATCH", path="/test"),
    ]

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_SWING_MODE,
            {ATTR_ENTITY_ID: entity_id, "swing_mode": "3"},
            blocking=True,
        )

    assert err.value.translation_key == "set_swing_mode_failed"
    assert mock_onecta_client.patch_characteristic.await_args_list == [
        call(
            DRY_FIXED_DIRECTION_GATEWAY_ID,
            "climateControl",
            "fanControl",
            FANMODE_FIXED,
            path="/operationModes/dry/fanDirection/vertical/currentMode",
        ),
        call(
            DRY_FIXED_DIRECTION_GATEWAY_ID,
            "climateControl",
            "fanControl",
            3,
            path="/operationModes/dry/fanDirection/vertical/modes/fixed",
        ),
    ]
    assert vertical.current_mode.value == FANMODE_FIXED
    assert vertical.modes is not None
    assert vertical.modes[FANMODE_FIXED].value == 2
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[ClimateEntityStateAttribute.SWING_MODE] == "2"


@pytest.mark.parametrize(
    ("configure_control", "service", "service_data", "feature", "translation_key"),
    [
        (
            _remove_fan_control,
            SERVICE_SET_FAN_MODE,
            {"fan_mode": "auto"},
            ClimateEntityFeature.FAN_MODE,
            "fan_control_unavailable",
        ),
        (
            _set_fan_speed_read_only,
            SERVICE_SET_FAN_MODE,
            {ClimateServiceArgument.FAN_MODE: "auto"},
            ClimateEntityFeature.FAN_MODE,
            "fan_mode_unavailable",
        ),
        (
            _set_vertical_swing_read_only,
            SERVICE_SET_SWING_MODE,
            {ClimateServiceArgument.SWING_MODE: SWING_ON},
            ClimateEntityFeature.SWING_MODE,
            "swing_control_unavailable",
        ),
        (
            _set_horizontal_swing_read_only,
            SERVICE_SET_SWING_HORIZONTAL_MODE,
            {ClimateServiceArgument.SWING_HORIZONTAL_MODE: SWING_ON},
            ClimateEntityFeature.SWING_HORIZONTAL_MODE,
            "swing_control_unavailable",
        ),
    ],
)
async def test_read_only_fan_controls_do_not_call_cloud(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    configure_control: Callable[[ManagementPoint], None],
    service: str,
    service_data: dict[str, str],
    feature: ClimateEntityFeature,
    translation_key: str,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Do not advertise or write read-only fan and swing telemetry."""
    await _async_setup_fixture(hass, config_entry, "ururu")
    coordinator = config_entry.runtime_data
    assert coordinator.data is not None
    device = next(iter(coordinator.data.values()))
    point = next(iter(device.device.management_points_by_type("climateControl")))
    configure_control(point)
    mock_onecta_client.patch_characteristic.reset_mock()
    entity_id = entity_registry.async_get_entity_id(
        Platform.CLIMATE, DOMAIN, f"{device.id}_{point.embedded_id}_roomTemperature"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[EntityStateAttribute.SUPPORTED_FEATURES] & feature
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id, **service_data},
            blocking=True,
        )
    assert err.value.translation_key == translation_key
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert not state.attributes[EntityStateAttribute.SUPPORTED_FEATURES] & feature
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id, **service_data},
            blocking=True,
        )
    mock_onecta_client.patch_characteristic.assert_not_awaited()


async def test_fan_mode_changes_with_hvac_mode(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Update the fan state from each native HVAC operation mode."""
    await _async_setup_fixture(hass, config_entry, "fanmode")
    entity_id = hass.states.async_entity_ids(CLIMATE_DOMAIN)[0]

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {
            "entity_id": entity_id,
            ClimateServiceArgument.HVAC_MODE: HVACMode.COOL,
        },
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == HVACMode.COOL
    assert state.attributes[ClimateEntityStateAttribute.FAN_MODE] == "3"

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {
            "entity_id": entity_id,
            ClimateServiceArgument.HVAC_MODE: HVACMode.DRY,
        },
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == HVACMode.DRY
    assert state.attributes[ClimateEntityStateAttribute.FAN_MODE] == "auto"
    assert mock_onecta_client.patch_characteristic.await_args_list == [
        call(
            "00000000-0000-4000-8000-000000000101",
            "climateControl",
            "onOffMode",
            "on",
            path=None,
        ),
        call(
            "00000000-0000-4000-8000-000000000101",
            "climateControl",
            "operationMode",
            "cooling",
            path=None,
        ),
        call(
            "00000000-0000-4000-8000-000000000101",
            "climateControl",
            "operationMode",
            "dry",
            path=None,
        ),
    ]


@pytest.mark.parametrize(
    (
        "current_mode",
        "mode_settable",
        "speed_settable",
        "fixed_min",
        "fixed_max",
        "fixed_step",
        "expected_modes",
    ),
    [
        pytest.param("quiet", False, True, 1, 2, 1, [], id="current-mode-read-only"),
        pytest.param("fixed", False, True, 1, 2, 1, ["1", "2"], id="fixed-position"),
        pytest.param(
            "fixed",
            True,
            False,
            1,
            2,
            1,
            ["quiet", "3"],
            id="current-fixed-speed-read-only",
        ),
        pytest.param(
            "fixed",
            True,
            True,
            None,
            None,
            None,
            ["quiet", "3"],
            id="settable-without-range",
        ),
        pytest.param(
            "quiet", True, False, 1, 2, 1, ["quiet"], id="fixed-speed-read-only"
        ),
        pytest.param(
            "quiet", True, True, 1, 2, 0, ["quiet"], id="zero-step-is-ignored"
        ),
    ],
)
async def test_climate_state_fan_modes_respect_writable_characteristics(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    current_mode: str,
    mode_settable: bool,
    speed_settable: bool,
    fixed_min: int | None,
    fixed_max: int | None,
    fixed_step: int | None,
    expected_modes: list[str],
) -> None:
    """Treat mode selection and numeric speed control as separate capabilities."""
    (
        entity_id,
        _,
        management_point,
        coordinator,
    ) = await _async_setup_climate_service_fixture(hass, config_entry, entity_registry)
    climate_control = management_point.climate_control
    assert climate_control is not None
    fan_operation = climate_control.fan_operation("heating")
    assert fan_operation is not None and fan_operation.fan_speed is not None
    fan_speed = fan_operation.fan_speed
    fan_speed.current_mode.value = current_mode
    fan_speed.current_mode.settable = mode_settable
    fan_speed.current_mode.values = ["quiet", FANMODE_FIXED]
    fixed = fan_speed.modes[FANMODE_FIXED]
    fixed.settable = speed_settable
    fixed.min_value = fixed_min
    fixed.max_value = fixed_max
    fixed.step_value = fixed_step
    coordinator.async_update_listeners()

    entity = hass.data[CLIMATE_DOMAIN].get_entity(entity_id)
    assert isinstance(entity, DaikinClimate)
    assert entity.fan_modes == expected_modes


@pytest.mark.parametrize(
    ("current_mode", "fixed_value"),
    [(None, 1), (FANMODE_FIXED, None)],
)
async def test_climate_state_omits_incomplete_fan_mode(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    current_mode: str | None,
    fixed_value: int | None,
) -> None:
    """Do not expose incomplete fixed fan data as a string in HA state."""
    (
        entity_id,
        _,
        management_point,
        coordinator,
    ) = await _async_setup_climate_service_fixture(hass, config_entry, entity_registry)
    climate_control = management_point.climate_control
    assert climate_control is not None
    fan_operation = climate_control.fan_operation("heating")
    assert fan_operation is not None and fan_operation.fan_speed is not None
    fan_speed = fan_operation.fan_speed
    fan_speed.current_mode.value = current_mode
    assert fan_speed.modes is not None
    fan_speed.modes[FANMODE_FIXED].value = fixed_value
    coordinator.async_update_listeners()

    entity = hass.data[CLIMATE_DOMAIN].get_entity(entity_id)
    assert isinstance(entity, DaikinClimate)
    assert entity.fan_mode is None


@pytest.mark.parametrize(
    ("initial_mode", "requested_mode", "expected_command"),
    [
        (FANMODE_FIXED, "quiet", "quiet"),
        ("quiet", "4", FANMODE_FIXED),
    ],
)
async def test_climate_service_translates_failed_fan_writes(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_onecta_client: MockOnectaClient,
    initial_mode: str,
    requested_mode: str,
    expected_command: str,
) -> None:
    """Translate Daikin errors from standard and fixed fan-mode commands."""
    (
        entity_id,
        gateway_id,
        management_point,
        coordinator,
    ) = await _async_setup_climate_service_fixture(hass, config_entry, entity_registry)
    climate_control = management_point.climate_control
    assert climate_control is not None
    fan_operation = climate_control.fan_operation("heating")
    assert fan_operation is not None and fan_operation.fan_speed is not None
    fan_operation.fan_speed.current_mode.value = initial_mode
    assert fan_operation.fan_speed.modes is not None
    fan_operation.fan_speed.modes[FANMODE_FIXED].value = 3
    coordinator.async_update_listeners()
    mock_onecta_client.patch_characteristic.side_effect = OnectaConnectionError(
        "test connection failure", method="PATCH", path="/test"
    )

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: entity_id, "fan_mode": requested_mode},
            blocking=True,
        )

    assert err.value.translation_key == "set_fan_mode_failed"
    assert mock_onecta_client.patch_characteristic.await_args.args == (
        gateway_id,
        management_point.embedded_id,
        "fanControl",
        expected_command,
    )
