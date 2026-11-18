"""Tests for the Daikin Onecta climate platform."""

from collections.abc import Callable
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call, patch

from daikin_onecta.exceptions import OnectaConnectionError
from daikin_onecta.models import ManagementPoint
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.climate import (
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
    ClimateEntity,
    ClimateEntityDescription,
    ClimateEntityFeature,
    ClimateEntityStateAttribute,
    ClimateServiceArgument,
    HVACMode,
)
from homeassistant.components.daikin_onecta.climate import (
    CLIMATE_ENTITY_DESCRIPTIONS,
    DaikinClimate,
    _create_climate_entities,
)
from homeassistant.components.daikin_onecta.const import FANMODE_FIXED
from homeassistant.components.daikin_onecta.coordinator import (
    OnectaDataUpdateCoordinator,
)
from homeassistant.config_entries import ConfigEntryState
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

from .conftest import DOMAIN, FAKE_ACCESS_TOKEN, MockOnectaClient
from .test_climate_snapshots import _async_setup_fixture


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


def test_create_climate_entities_deduplicates_targets_per_management_point() -> None:
    """Create one entity per temperature target, not per operation mode."""
    management_point = SimpleNamespace(
        embedded_id="main_zone",
        climate_control=SimpleNamespace(
            setpoint_types=[
                "roomTemperature",
                "leavingWaterOffset",
                "leavingWaterTemperature",
                "unknownTemperature",
            ]
        ),
    )
    device = MagicMock()
    device.device.management_points_by_type.return_value = [management_point]
    coordinator = MagicMock()

    with patch(
        "homeassistant.components.daikin_onecta.climate.DaikinClimate"
    ) as climate:
        _create_climate_entities(device, coordinator)

    assert climate.call_args_list == [
        (
            (
                device,
                "roomTemperature",
                coordinator,
                "main_zone",
                CLIMATE_ENTITY_DESCRIPTIONS["roomTemperature"],
            ),
            {},
        ),
        (
            (
                device,
                "leavingWaterOffset",
                coordinator,
                "main_zone",
                CLIMATE_ENTITY_DESCRIPTIONS["leavingWaterOffset"],
            ),
            {},
        ),
        (
            (
                device,
                "leavingWaterTemperature",
                coordinator,
                "main_zone",
                CLIMATE_ENTITY_DESCRIPTIONS["leavingWaterTemperature"],
            ),
            {},
        ),
    ]


def test_create_climate_entities_skips_management_points_without_climate_control() -> (
    None
):
    """Skip management points that do not expose climate controls."""
    management_point = SimpleNamespace(
        embedded_id="zone",
        climate_control=None,
    )
    device = MagicMock()
    device.device.management_points_by_type.return_value = [management_point]

    assert _create_climate_entities(device, MagicMock()) == []


@pytest.mark.parametrize(
    ("failure", "expected_available"),
    [
        (None, True),
        ("coordinator", False),
        ("gateway", False),
        ("management_point", False),
    ],
)
async def test_climate_entity_availability(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    failure: str | None,
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
    if failure == "coordinator":
        coordinator.last_update_success = False
    elif failure == "gateway":
        device.mark_unavailable()
    elif failure == "management_point":
        device.device.management_points.remove(management_point)
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

    enabled_value = (
        holiday_mode.value.enabled
        if native_characteristic == "holidayMode"
        else powerful_mode.value
    )
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

    disabled_value = (
        holiday_mode.value.enabled
        if native_characteristic == "holidayMode"
        else powerful_mode.value
    )
    assert disabled_value in {False, "off"}
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[ClimateEntityStateAttribute.PRESET_MODE] == PRESET_NONE
    if native_characteristic == "holidayMode":
        assert mock_onecta_client.post_management_point.await_count == 2
        assert mock_onecta_client.post_management_point.await_args_list[0].args[:3] == (
            gateway_id,
            management_point.embedded_id,
            "holiday-mode",
        )
        assert (
            mock_onecta_client.post_management_point.await_args_list[0].args[3][
                "enabled"
            ]
            is True
        )
        assert mock_onecta_client.post_management_point.await_args_list[1].args == (
            gateway_id,
            management_point.embedded_id,
            "holiday-mode",
            {"enabled": False},
        )
    else:
        assert mock_onecta_client.patch_characteristic.await_count == 2
        assert all(
            call_args.args[:3]
            == (gateway_id, management_point.embedded_id, native_characteristic)
            for call_args in mock_onecta_client.patch_characteristic.await_args_list
        )


@pytest.mark.parametrize(
    ("target_preset", "initial_value", "expected_state"),
    [
        (PRESET_BOOST, "off", PRESET_NONE),
        (PRESET_NONE, "on", PRESET_BOOST),
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
        "on" if target_preset == PRESET_BOOST else "off",
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
    ("case", "expected_state"),
    [
        ("missing_power", HVACMode.HEAT_COOL),
        ("unknown_power", "unknown"),
        ("missing_operation", "unknown"),
        ("omitted_operation", "unknown"),
    ],
)
async def test_climate_state_handles_missing_hvac_data(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    case: str,
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
    replacement_management_point = management_point
    if case == "missing_power":
        replacement_management_point = replace(management_point, on_off_mode=None)
        assert replacement_management_point.operation_mode is not None
        replacement_management_point.operation_mode.value = "auto"
    elif case == "unknown_power":
        assert climate_control.on_off_mode is not None
        climate_control.on_off_mode.value = None
    elif case == "missing_operation":
        assert climate_control.on_off_mode is not None
        climate_control.on_off_mode.value = "on"
        replacement_management_point = replace(management_point, operation_mode=None)
    else:
        assert climate_control.on_off_mode is not None
        climate_control.on_off_mode.value = "on"
        climate_control.operation_mode.value = None
    if case in {"missing_power", "missing_operation"}:
        device = next(iter(coordinator.data.values()))
        device.set_device_data(
            replace(
                device.device,
                management_points=[
                    replacement_management_point
                    if point.embedded_id == management_point.embedded_id
                    else point
                    for point in device.device.management_points
                ],
            )
        )
    coordinator.async_update_listeners()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state


async def test_climate_state_does_not_advertise_read_only_off_mode(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Keep observed off state while excluding the unwritable off mode option."""
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
    assert HVACMode.OFF not in entity.hvac_modes


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
    ("service", "argument", "value", "path", "control"),
    [
        (
            SERVICE_SET_FAN_MODE,
            "fan_mode",
            "quiet",
            "/operationModes/heating/fanSpeed/currentMode",
            "fan_speed",
        ),
        (
            SERVICE_SET_SWING_MODE,
            "swing_mode",
            SWING_ON,
            "/operationModes/heating/fanDirection/vertical/currentMode",
            "vertical_swing",
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
    control: str,
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
    heating_operation = climate_control.fan_operation("heating")
    cooling_operation = climate_control.fan_operation("cooling")
    assert heating_operation is not None and cooling_operation is not None

    if control == "fan_speed":
        assert heating_operation.fan_speed is not None
        assert cooling_operation.fan_speed is not None
        captured_mode = heating_operation.fan_speed.current_mode.value
        active_mode = cooling_operation.fan_speed.current_mode.value
    else:
        assert heating_operation.fan_direction is not None
        assert cooling_operation.fan_direction is not None
        assert heating_operation.fan_direction.vertical is not None
        assert cooling_operation.fan_direction.vertical is not None
        captured_mode = heating_operation.fan_direction.vertical.current_mode.value
        active_mode = cooling_operation.fan_direction.vertical.current_mode.value

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
        "quiet" if control == "fan_speed" else "swing",
        path=path,
    )
    if control == "fan_speed":
        assert heating_operation.fan_speed.current_mode.value == "quiet"
        assert cooling_operation.fan_speed.current_mode.value == active_mode
    else:
        assert heating_operation.fan_direction.vertical.current_mode.value == "swing"
        assert (
            cooling_operation.fan_direction.vertical.current_mode.value == active_mode
        )
    assert captured_mode != value


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
    for name in ("holidayMode", "powerfulMode", "comfortMode", "econoMode"):
        preset = climate_control.mode_characteristic(name)
        if preset is not None:
            preset.settable = False
    coordinator.async_update_listeners()

    entity = hass.data[CLIMATE_DOMAIN].get_entity(entity_id)
    assert entity is not None
    assert entity.preset_modes == [PRESET_NONE]


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


@pytest.mark.parametrize("patch_result", [True, False])
async def test_climate_service_updates_entity_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    patch_result: bool,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Test climate services through the Home Assistant integration API."""
    setpoint = SimpleNamespace(
        value=20, min_value=7, max_value=30, step_value=1, settable=True, unit=None
    )
    operation_mode = SimpleNamespace(value="heating", values=["heating"], settable=True)
    climate_control = MagicMock(
        embedded_id="zone", management_point_type="climateControl"
    )
    climate_control.name = None
    climate_control.temperature_control = SimpleNamespace(
        value=SimpleNamespace(
            operation_modes={
                "heating": SimpleNamespace(setpoints={"roomTemperature": setpoint})
            }
        )
    )
    climate_control.operation_mode = operation_mode
    climate_control.on_off_mode = SimpleNamespace(value="on", settable=True)
    climate_control.fan_control = None
    climate_control.holiday_mode = None
    climate_control.sensory_data = MagicMock(return_value=None)
    climate_control.characteristic.return_value = None
    climate_control.climate_control = climate_control
    climate_control.setpoint_types = ["roomTemperature"]
    climate_control.setpoint.return_value = setpoint
    climate_control.fan_operation.return_value = None
    climate_control.mode_characteristic.return_value = None
    climate_control.current_temperature.return_value = None

    device = MagicMock(id="gateway", available=True)
    device.name = "Daikin"
    device.device = SimpleNamespace(
        device_model="Daikin",
        gateway_embedded_id=None,
        gateway_management_point=None,
        mac_address=None,
        management_points_by_type=lambda _: (climate_control,),
    )
    device.gateway_metadata = (None, None, None)
    device.management_point.return_value = climate_control
    if not patch_result:
        mock_onecta_client.patch_characteristic.side_effect = OnectaConnectionError(
            "test connection failure", method="PATCH", path="/test"
        )
    gateway_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, device.id)},
        manufacturer="Daikin",
        name=device.name,
    )

    coordinator = OnectaDataUpdateCoordinator(hass, config_entry, MagicMock())
    coordinator.data = {device.id: device}
    coordinator.last_update_success = True
    coordinator.async_config_entry_first_refresh = AsyncMock()
    coordinator.async_get_access_token = AsyncMock()

    with (
        patch(
            "homeassistant.components.daikin_onecta."
            "config_entry_oauth2_flow.async_get_config_entry_implementation"
        ),
        patch(
            "homeassistant.components.daikin_onecta.OnectaDataUpdateCoordinator.async_get_access_token",
            AsyncMock(),
        ),
        patch(
            "homeassistant.components.daikin_onecta.OnectaDataUpdateCoordinator",
            return_value=coordinator,
        ),
        patch("homeassistant.components.daikin_onecta.PLATFORMS", [Platform.CLIMATE]),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        Platform.CLIMATE, DOMAIN, "gateway_zone_roomTemperature"
    )
    assert entity_id == "climate.daikin_room_temperature"
    child_entry = device_registry.async_get_child_device_by_identifier(
        (DOMAIN, "gateway_zone"), config_entry.entry_id
    )
    assert child_entry is None
    assert entity_registry.async_get(entity_id).device_id == gateway_entry.id

    service_call = hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: entity_id, ClimateServiceArgument.TEMPERATURE: 21},
        blocking=True,
    )
    if patch_result:
        await service_call
        expected_temperature = 21
    else:
        with pytest.raises(HomeAssistantError) as err:
            await service_call
        assert err.value.translation_domain == DOMAIN
        assert err.value.translation_key == "set_temperature_failed"
        assert str(err.value) == "Failed to set the temperature for Daikin"
        expected_temperature = 20

    state = hass.states.get(entity_id)
    assert state is not None
    assert (
        state.attributes[ClimateEntityStateAttribute.TARGET_TEMPERATURE]
        == expected_temperature
    )

    mock_onecta_client.patch_characteristic.assert_awaited_once_with(
        "gateway",
        "zone",
        "temperatureControl",
        21,
        path="/operationModes/heating/setpoints/roomTemperature",
    )

    device.async_update_device_registry.reset_mock()
    coordinator.async_update_listeners()


async def test_climate_service_rejected_token_preserves_entity_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Translate rejected credentials when a climate action reaches Daikin."""
    response = MagicMock(status=401, headers={})
    response.text = AsyncMock(return_value="Unauthorized")
    request_context = MagicMock()
    request_context.__aenter__ = AsyncMock(return_value=response)
    request_context.__aexit__ = AsyncMock(return_value=None)
    session = MagicMock()
    session.request = MagicMock(return_value=request_context)
    with patch(
        "homeassistant.components.daikin_onecta.coordinator.async_get_clientsession",
        return_value=session,
    ):
        await _async_setup_fixture(hass, config_entry, "climate_fixedfanmode")
    coordinator = config_entry.runtime_data
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
    session.request.assert_called_once()
    request = session.request
    assert request.call_args.args == (
        "PATCH",
        "https://api.onecta.daikineurope.com/v1/gateway-devices/"
        f"{next(iter(coordinator.data))}/management-points/climateControl/"
        "characteristics/temperatureControl",
    )
    assert request.call_args.kwargs["headers"]["Authorization"] == (
        f"Bearer {FAKE_ACCESS_TOKEN}"
    )
    assert request.call_args.kwargs["json"] == {
        "value": 22,
        "path": "/operationModes/heating/setpoints/roomTemperature",
    }


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
        (
            SERVICE_SET_HVAC_MODE,
            {ClimateServiceArgument.HVAC_MODE: HVACMode.OFF},
            "on",
        ),
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
    assert coordinator.last_patch_call is None


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

    setpoint = entity._get_setpoint()
    cc = entity._climate_control()
    assert setpoint is not None
    assert cc is not None
    setpoint.unit = setpoint_unit
    sensory_target = (
        "leavingWaterTemperature"
        if entity._setpoint == "leavingWaterOffset"
        else entity._setpoint
    )
    sensory_data = cc.sensory_data(sensory_target)
    if sensory_data is not None:
        sensory_data.unit = sensory_unit
    config_entry.runtime_data.async_update_listeners()

    assert entity.native_temperature_unit == expected_unit


async def test_climate_platform_services_and_management_points(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Test platform services with real entities for two management points."""

    def climate_control(embedded_id: str, target_temperature: int) -> SimpleNamespace:
        setpoint = SimpleNamespace(
            value=target_temperature,
            min_value=7,
            max_value=30,
            step_value=1,
            settable=True,
            unit=None,
        )
        fan_operation = SimpleNamespace(
            fan_speed=SimpleNamespace(
                current_mode=SimpleNamespace(
                    settable=True, value="auto", values=["auto", "quiet"]
                ),
                modes={},
            ),
            fan_direction=SimpleNamespace(
                vertical=SimpleNamespace(
                    current_mode=SimpleNamespace(
                        settable=True, value="stop", values=["stop", "swing"]
                    )
                ),
                horizontal=SimpleNamespace(
                    current_mode=SimpleNamespace(
                        settable=True, value="stop", values=["stop", "swing"]
                    )
                ),
            ),
        )
        presets = {
            "powerfulMode": SimpleNamespace(value="off", settable=True),
            "comfortMode": SimpleNamespace(value="off", settable=True),
            "econoMode": SimpleNamespace(value="off", settable=True),
        }
        control = SimpleNamespace(
            embedded_id=embedded_id,
            management_point_type="climateControl",
            model=None,
            serial=None,
            version=None,
            name=SimpleNamespace(
                value=embedded_id.replace("_", " ").title(),
            ),
            operation_mode=SimpleNamespace(
                value="heating", values=["heating", "cooling"], settable=True
            ),
            on_off_mode=SimpleNamespace(value="on", settable=True),
            holiday_mode=SimpleNamespace(value=SimpleNamespace(enabled=False)),
        )
        control.climate_control = control
        control.setpoint_types = ["roomTemperature"]
        control.setpoint = lambda _target, _mode=None: setpoint
        control.fan_operation = lambda _mode=None: fan_operation
        control.mode_characteristic = presets.get
        control.current_temperature = lambda _target: None
        control.sensory_data = lambda _target: None
        error_state = SimpleNamespace(value=False, settable=False, values=None)
        control.scalar_characteristics = lambda: {"isInErrorState": error_state}
        control.scalar_characteristic = lambda _name: error_state
        return control

    climate_controls = {
        "living_room": climate_control("living_room", 20),
        "bedroom": climate_control("bedroom", 18),
    }
    climate_controls["bedroom"].name = None
    device = MagicMock(id="gateway", available=True)
    device.name = "Daikin"
    device.device = SimpleNamespace(
        device_model="Daikin",
        gateway_embedded_id=None,
        gateway_management_point=None,
        mac_address=None,
        management_points=tuple(climate_controls.values()),
        management_points_by_type=lambda _: tuple(climate_controls.values()),
    )
    device.gateway_metadata = (None, None, None)
    device.management_point.side_effect = climate_controls.get
    coordinator = OnectaDataUpdateCoordinator(hass, config_entry, MagicMock())
    coordinator.data = {device.id: device}
    coordinator.last_update_success = True
    coordinator.async_config_entry_first_refresh = AsyncMock()

    with (
        patch(
            "homeassistant.components.daikin_onecta."
            "config_entry_oauth2_flow.async_get_config_entry_implementation"
        ),
        patch(
            "homeassistant.components.daikin_onecta.OnectaDataUpdateCoordinator.async_get_access_token",
            AsyncMock(),
        ),
        patch(
            "homeassistant.components.daikin_onecta.OnectaDataUpdateCoordinator",
            return_value=coordinator,
        ),
        patch(
            "homeassistant.components.daikin_onecta.PLATFORMS",
            [Platform.CLIMATE, Platform.BINARY_SENSOR],
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

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
    assert (
        living_room_state.attributes[ClimateEntityStateAttribute.TARGET_TEMPERATURE]
        == 21
    )
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

    for service, argument, state_attribute in (
        (SERVICE_SET_SWING_MODE, "swing_mode", ClimateEntityStateAttribute.SWING_MODE),
        (
            SERVICE_SET_SWING_HORIZONTAL_MODE,
            "swing_horizontal_mode",
            ClimateEntityStateAttribute.SWING_HORIZONTAL_MODE,
        ),
    ):
        mock_onecta_client.patch_characteristic.side_effect = OnectaConnectionError(
            "test connection failure", method="PATCH", path="/test"
        )
        with pytest.raises(HomeAssistantError) as err:
            await call_service(service, **{argument: SWING_OFF})
        assert err.value.translation_key == "set_swing_mode_failed"
        state_after_failure = hass.states.get(living_room_entity_id)
        assert state_after_failure is not None
        assert state_after_failure.attributes[state_attribute] == SWING_ON
        mock_onecta_client.patch_characteristic.side_effect = None

    mock_onecta_client.patch_characteristic.reset_mock()
    unavailable_controls = (
        (
            "vertical_swing",
            SERVICE_SET_SWING_MODE,
            "swing_mode",
            SWING_OFF,
            "swing_control_unavailable",
        ),
        (
            "horizontal_swing",
            SERVICE_SET_SWING_HORIZONTAL_MODE,
            "swing_horizontal_mode",
            SWING_OFF,
            "swing_control_unavailable",
        ),
        (
            "preset",
            SERVICE_SET_PRESET_MODE,
            "preset_mode",
            PRESET_BOOST,
            "preset_mode_unavailable",
        ),
    )
    for control, service, argument, value, translation_key in unavailable_controls:
        if control == "preset":
            characteristic = climate_controls["living_room"].mode_characteristic(
                "powerfulMode"
            )
            assert characteristic is not None
            characteristic.settable = False
        else:
            direction = "vertical" if control == "vertical_swing" else "horizontal"
            fan_operation = climate_controls["living_room"].fan_operation()
            assert fan_operation is not None
            assert fan_operation.fan_direction is not None
            axis = getattr(fan_operation.fan_direction, direction)
            assert axis is not None
            axis.current_mode.settable = False

        with pytest.raises(ServiceValidationError) as err:
            await call_service(service, **{argument: value})
        assert err.value.translation_key == translation_key

    setpoint = climate_controls["living_room"].setpoint("roomTemperature")
    assert setpoint is not None
    setpoint.settable = False
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

    assert setpoint.value == expected_temperature
    if should_write:
        mock_onecta_client.patch_characteristic.assert_awaited_once_with(
            gateway_id,
            point.embedded_id,
            "temperatureControl",
            expected_temperature,
            path="/operationModes/heating/setpoints/roomTemperature",
        )
    else:
        mock_onecta_client.patch_characteristic.assert_not_awaited()


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


async def test_setup_creates_entities_per_management_point(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Set up a separate climate entity for each climate-control zone."""
    coordinator = MagicMock()
    gateway = MagicMock(id="device", device_model="Daikin")
    onecta_device = MagicMock(id="device", device=gateway)
    coordinator.data = {"device": onecta_device}
    first_zone = MagicMock(embedded_id="first_zone")
    first_zone.climate_control.setpoint_types = ["roomTemperature"]
    second_zone = MagicMock(embedded_id="second_zone")
    second_zone.climate_control.setpoint_types = ["roomTemperature"]
    gateway.management_points_by_type.return_value = (first_zone, second_zone)
    coordinator.async_config_entry_first_refresh = AsyncMock()
    coordinator.async_get_access_token = AsyncMock()

    class TestClimateEntity(ClimateEntity):
        """Minimal climate entity used to observe platform setup."""

        def __init__(
            self,
            device: MagicMock,
            setpoint: str,
            coordinator: MagicMock,
            embedded_id: str,
            description: ClimateEntityDescription,
        ) -> None:
            """Initialize the test entity."""
            self._attr_unique_id = f"{device.id}_{embedded_id}_{setpoint}"
            self._attr_native_temperature_unit = UnitOfTemperature.CELSIUS
            self._attr_hvac_mode = HVACMode.HEAT
            self._attr_hvac_modes = [HVACMode.OFF]

    with (
        patch(
            "homeassistant.components.daikin_onecta."
            "config_entry_oauth2_flow.async_get_config_entry_implementation"
        ),
        patch(
            "homeassistant.components.daikin_onecta.OnectaDataUpdateCoordinator.async_get_access_token",
            AsyncMock(),
        ),
        patch(
            "homeassistant.components.daikin_onecta.OnectaDataUpdateCoordinator",
            return_value=coordinator,
        ),
        patch("homeassistant.components.daikin_onecta.PLATFORMS", [Platform.CLIMATE]),
        patch(
            "homeassistant.components.daikin_onecta.climate.DaikinClimate",
            TestClimateEntity,
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert entity_registry.async_get_entity_id(
        Platform.CLIMATE, DOMAIN, "device_first_zone_roomTemperature"
    )
    assert entity_registry.async_get_entity_id(
        Platform.CLIMATE, DOMAIN, "device_second_zone_roomTemperature"
    )


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
    fan_operation = climate_control.fan_operation("heating")
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
    ("control", "service", "service_data", "feature"),
    [
        (
            "missing",
            SERVICE_SET_FAN_MODE,
            {"fan_mode": "auto"},
            ClimateEntityFeature.FAN_MODE,
        ),
        (
            "speed",
            SERVICE_SET_FAN_MODE,
            {ClimateServiceArgument.FAN_MODE: "auto"},
            ClimateEntityFeature.FAN_MODE,
        ),
        (
            "vertical",
            SERVICE_SET_SWING_MODE,
            {ClimateServiceArgument.SWING_MODE: SWING_ON},
            ClimateEntityFeature.SWING_MODE,
        ),
        (
            "horizontal",
            SERVICE_SET_SWING_HORIZONTAL_MODE,
            {ClimateServiceArgument.SWING_HORIZONTAL_MODE: SWING_ON},
            ClimateEntityFeature.SWING_HORIZONTAL_MODE,
        ),
    ],
)
async def test_read_only_fan_controls_do_not_call_cloud(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    control: str,
    service: str,
    service_data: dict[str, str],
    feature: ClimateEntityFeature,
) -> None:
    """Do not advertise or write read-only fan and swing telemetry."""
    await _async_setup_fixture(hass, config_entry, "ururu")
    coordinator = config_entry.runtime_data
    assert coordinator.data is not None
    device = next(iter(coordinator.data.values()))
    point = next(iter(device.device.management_points_by_type("climateControl")))
    assert point.climate_control is not None
    fan = point.climate_control.fan_operation()
    assert fan is not None
    assert fan.fan_speed is not None
    assert fan.fan_direction is not None
    assert fan.fan_direction.vertical is not None
    assert fan.fan_direction.horizontal is not None
    if control == "missing":
        point.fan_control = None
    else:
        characteristic = {
            "speed": fan.fan_speed.current_mode,
            "vertical": fan.fan_direction.vertical.current_mode,
            "horizontal": fan.fan_direction.horizontal.current_mode,
        }[control]
        characteristic.settable = False
    coordinator.client.patch_characteristic = AsyncMock()
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
    assert (
        err.value.translation_key
        == {
            "missing": "fan_control_unavailable",
            "speed": "fan_mode_unavailable",
            "vertical": "swing_control_unavailable",
            "horizontal": "swing_control_unavailable",
        }[control]
    )
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
    coordinator.client.patch_characteristic.assert_not_awaited()


@pytest.mark.parametrize(
    ("current_mode", "mode_settable", "speed_settable", "expected_modes"),
    [
        ("quiet", False, True, []),
        ("fixed", False, True, ["1", "2"]),
        ("quiet", True, False, ["quiet"]),
    ],
)
async def test_climate_state_fan_modes_respect_writable_characteristics(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    current_mode: str,
    mode_settable: bool,
    speed_settable: bool,
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
    fixed.min_value = 1
    fixed.max_value = 2
    fixed.step_value = 1
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
    if fixed_value is not None or current_mode == FANMODE_FIXED:
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
    if requested_mode.isnumeric():
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
