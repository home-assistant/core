"""Tests for the Daikin Onecta climate platform."""

from collections.abc import Callable
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call, patch

from daikin_onecta import ClimateControlClient
from daikin_onecta.exceptions import OnectaConnectionError
from daikin_onecta.models import ManagementPoint
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_COMFORT,
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
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util.unit_system import (
    METRIC_SYSTEM,
    US_CUSTOMARY_SYSTEM,
    UnitSystem,
)

from .conftest import DOMAIN, FAKE_ACCESS_TOKEN, MockOnectaClient
from .test_climate_snapshots import _async_setup_fixture


async def _replay_command(coordinator: MagicMock) -> AsyncMock:
    """Run a captured coordinator command against a minimal library client."""
    command = coordinator.async_execute_command.await_args.args[0]
    client = MagicMock()
    client.patch_characteristic = AsyncMock()
    client.climate_control.side_effect = lambda gateway_id, management_point_id: (
        ClimateControlClient(client, gateway_id, management_point_id)
    )
    await command(client)
    return client.patch_characteristic


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


def test_get_hvac_mode_without_climate_control() -> None:
    """Return an unknown HVAC mode when climate data is absent."""
    entity = object.__new__(DaikinClimate)
    entity._climate_control = MagicMock(return_value=None)

    assert entity._get_hvac_mode() is None


@pytest.mark.parametrize(
    ("last_update_success", "device_available", "management_point_exists", "expected"),
    [
        (True, True, True, True),
        (False, True, True, False),
        (True, False, True, False),
        (True, True, False, False),
    ],
)
def test_climate_availability(
    last_update_success: bool,
    device_available: bool,
    management_point_exists: bool,
    expected: bool,
) -> None:
    """Climate entities require a successful update and present management point."""
    entity = object.__new__(DaikinClimate)
    entity.coordinator = MagicMock(last_update_success=last_update_success)
    entity._device = MagicMock(available=device_available)
    entity._device.management_point.return_value = (
        SimpleNamespace(
            climate_control=SimpleNamespace(setpoint_types=["roomTemperature"])
        )
        if management_point_exists
        else None
    )
    entity._embedded_id = "zone"
    entity._setpoint = "roomTemperature"

    assert entity.available is expected

    if expected:
        entity._setpoint = "leavingWaterTemperature"
        assert not entity.available


async def test_async_climate_command_uses_bound_library_client() -> None:
    """Pass stable IDs to the bound climate-control library client."""
    entity = object.__new__(DaikinClimate)
    client = MagicMock()
    climate = MagicMock()
    climate.set_fan_mode = AsyncMock()
    client.climate_control.return_value = climate

    async def execute_command(command: object) -> bool:
        await command(client)  # type: ignore[operator]
        return True

    api = MagicMock()
    api.async_execute_command = AsyncMock(side_effect=execute_command)
    device = MagicMock()
    device.id = "gateway"
    object.__setattr__(entity, "_device", device)
    object.__setattr__(entity, "_embedded_id", "zone")
    entity.coordinator = api

    assert await entity._async_execute_climate_command(
        lambda bound_client: bound_client.set_fan_mode("heating", "quiet")
    )

    client.climate_control.assert_called_once_with("gateway", "zone")
    climate.set_fan_mode.assert_awaited_once_with("heating", "quiet")


async def test_set_fixed_fan_mode_updates_cached_speed() -> None:
    """Write a fixed fan speed and update the captured cached operation mode."""
    entity = object.__new__(DaikinClimate)
    device = MagicMock()
    device.id = "device"
    coordinator = MagicMock()
    coordinator.async_execute_command = AsyncMock(return_value=True)
    fan_speed = SimpleNamespace(
        current_mode=SimpleNamespace(
            settable=True, value=FANMODE_FIXED, values=[FANMODE_FIXED]
        ),
        modes={FANMODE_FIXED: SimpleNamespace(value=1, settable=True)},
    )
    object.__setattr__(entity, "_device", device)
    object.__setattr__(entity, "_embedded_id", "zone")
    entity.coordinator = coordinator
    entity._fan_operation = MagicMock(return_value=SimpleNamespace(fan_speed=fan_speed))
    entity._climate_control = MagicMock(
        return_value=SimpleNamespace(operation_mode=SimpleNamespace(value="heating"))
    )
    entity._get_fan_modes = MagicMock(return_value=["2"])
    entity._get_fan_mode = MagicMock(return_value="2")

    await entity.async_set_fan_mode("2")

    (await _replay_command(coordinator)).assert_awaited_once_with(
        "device",
        "zone",
        "fanControl",
        2,
        path="/operationModes/heating/fanSpeed/modes/fixed",
    )
    assert fan_speed.modes[FANMODE_FIXED].value == 2
    coordinator.async_update_listeners.assert_called_once_with()


async def test_enable_and_disable_away_preset_updates_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use the typed holiday command and update the cached holiday state."""
    entity = object.__new__(DaikinClimate)
    device = MagicMock(id="device", name="Device")
    holiday_mode = SimpleNamespace(value=SimpleNamespace(enabled=False))
    client = MagicMock()
    climate = MagicMock()
    climate.set_holiday_mode = AsyncMock()
    client.climate_control.return_value = climate

    async def execute_command(command: object) -> bool:
        await command(client)  # type: ignore[operator]
        return True

    api = MagicMock()
    api.async_execute_command = AsyncMock(side_effect=execute_command)
    object.__setattr__(entity, "_device", device)
    object.__setattr__(entity, "_embedded_id", "zone")
    object.__setattr__(entity, "_attr_hvac_mode", HVACMode.HEAT)
    entity.coordinator = api
    entity._preset_characteristic = MagicMock(return_value=holiday_mode)
    with patch(
        "homeassistant.components.daikin_onecta.climate.dt_util.now",
        return_value=datetime(2026, 10, 6),
    ):
        assert await entity._async_enable_preset_mode(PRESET_AWAY)

    client.climate_control.assert_called_once_with("device", "zone")
    climate.set_holiday_mode.assert_awaited_once_with(
        True,
        start_date=datetime(2026, 10, 6).date(),
        end_date=datetime(2026, 12, 5).date(),
    )
    assert holiday_mode.value.enabled

    assert await entity._async_disable_preset_mode(PRESET_AWAY)

    climate.set_holiday_mode.assert_awaited_with(False)
    assert not holiday_mode.value.enabled


async def test_enable_and_disable_preset_updates_cache() -> None:
    """Update a non-holiday preset only after its cloud command succeeds."""
    entity = object.__new__(DaikinClimate)
    device = MagicMock(id="device", name="Device")
    coordinator = MagicMock()
    coordinator.async_execute_command = AsyncMock(return_value=True)
    powerful_mode = SimpleNamespace(value="off")
    object.__setattr__(entity, "_device", device)
    object.__setattr__(entity, "_embedded_id", "zone")
    object.__setattr__(entity, "_attr_hvac_mode", HVACMode.HEAT)
    entity.coordinator = coordinator
    entity._preset_characteristic = MagicMock(return_value=powerful_mode)

    assert await entity._async_enable_preset_mode(PRESET_BOOST)
    assert powerful_mode.value == "on"
    assert await entity._async_disable_preset_mode(PRESET_BOOST)
    assert powerful_mode.value == "off"

    assert coordinator.async_execute_command.await_count == 2


@pytest.mark.parametrize(
    ("method", "initial_value"),
    [
        ("_async_enable_preset_mode", "off"),
        ("_async_disable_preset_mode", "on"),
    ],
)
async def test_preset_command_failure_keeps_cached_state(
    method: str, initial_value: str
) -> None:
    """Leave the cached preset unchanged when Daikin rejects its command."""
    entity = object.__new__(DaikinClimate)
    device = MagicMock()
    device.id = "device"
    device.name = "Device"
    coordinator = MagicMock()
    coordinator.async_execute_command = AsyncMock(return_value=False)
    powerful_mode = SimpleNamespace(value=initial_value)
    object.__setattr__(entity, "_device", device)
    object.__setattr__(entity, "_embedded_id", "zone")
    object.__setattr__(entity, "_attr_hvac_mode", HVACMode.HEAT)
    entity.coordinator = coordinator
    entity._preset_characteristic = MagicMock(return_value=powerful_mode)

    assert not await getattr(entity, method)(PRESET_BOOST)

    assert powerful_mode.value == initial_value


@pytest.mark.parametrize(
    ("method", "initial_value"),
    [("async_turn_on", "off"), ("async_turn_off", "on")],
)
async def test_turn_handles_management_point_removed_after_command(
    method: str, initial_value: str
) -> None:
    """Do not update stale cached state after its management point disappears."""
    entity = object.__new__(DaikinClimate)
    device = MagicMock()
    device.id = "device"
    device.name = "Device"
    coordinator = MagicMock()
    coordinator.async_execute_command = AsyncMock(return_value=True)
    climate_control = SimpleNamespace(
        on_off_mode=SimpleNamespace(value=initial_value, settable=True)
    )
    object.__setattr__(entity, "_device", device)
    object.__setattr__(entity, "_embedded_id", "zone")
    entity.coordinator = coordinator
    entity._climate_control = MagicMock(side_effect=[climate_control, None])

    await getattr(entity, method)()

    coordinator.async_execute_command.assert_awaited_once()
    coordinator.async_update_listeners.assert_not_called()


@pytest.mark.parametrize(
    ("method", "initial_value", "translation_key"),
    [
        ("async_turn_on", "off", "turn_on_failed"),
        ("async_turn_off", "on", "turn_off_failed"),
    ],
)
async def test_turn_keeps_cached_power_state_after_failed_command(
    method: str,
    initial_value: str,
    translation_key: str,
) -> None:
    """Do not publish an unsuccessful power command."""
    entity = object.__new__(DaikinClimate)
    device = MagicMock(id="device", name="Device")
    coordinator = MagicMock()
    coordinator.async_execute_command = AsyncMock(return_value=False)
    climate_control = SimpleNamespace(
        on_off_mode=SimpleNamespace(value=initial_value, settable=True)
    )
    object.__setattr__(entity, "_device", device)
    object.__setattr__(entity, "_embedded_id", "zone")
    entity.coordinator = coordinator
    entity._climate_control = MagicMock(return_value=climate_control)

    with pytest.raises(HomeAssistantError) as err:
        await getattr(entity, method)()

    assert err.value.translation_key == translation_key
    assert climate_control.on_off_mode.value == initial_value
    coordinator.async_update_listeners.assert_not_called()


async def test_set_hvac_mode_publishes_successful_power_write() -> None:
    """Publish a successful power write before a failed mode write."""
    entity = object.__new__(DaikinClimate)
    device = MagicMock(id="device")
    device.name = "Device"
    coordinator = MagicMock()
    coordinator.async_execute_command = AsyncMock(side_effect=[True, False])
    climate_control = SimpleNamespace(
        on_off_mode=SimpleNamespace(value="off", settable=True),
        operation_mode=SimpleNamespace(
            value="cooling", settable=True, values=["cooling", "heating"]
        ),
    )
    object.__setattr__(entity, "_device", device)
    object.__setattr__(entity, "_embedded_id", "zone")
    object.__setattr__(entity, "_attr_hvac_mode", HVACMode.OFF)
    entity.coordinator = coordinator
    entity._climate_control = MagicMock(return_value=climate_control)
    entity._update_state = MagicMock()

    with pytest.raises(HomeAssistantError) as err:
        await entity.async_set_hvac_mode(HVACMode.HEAT)

    assert err.value.translation_key == "set_hvac_mode_failed"

    assert climate_control.on_off_mode.value == "on"
    assert climate_control.operation_mode.value == "cooling"
    entity._update_state.assert_called_once_with()
    coordinator.async_update_listeners.assert_called_once_with()


async def test_set_hvac_mode_updates_replaced_management_point() -> None:
    """Update the current model when polling replaces it during a command."""
    entity = object.__new__(DaikinClimate)
    device = MagicMock(id="device")
    device.name = "Device"
    coordinator = MagicMock()
    coordinator.async_execute_command = AsyncMock(return_value=True)
    previous_management_point = SimpleNamespace(
        on_off_mode=SimpleNamespace(value="off", settable=True),
        operation_mode=SimpleNamespace(
            value="heating", settable=True, values=["heating", "cooling"]
        ),
    )
    current_management_point = SimpleNamespace(
        on_off_mode=SimpleNamespace(value="off", settable=True),
        operation_mode=SimpleNamespace(
            value="heating", settable=True, values=["heating", "cooling"]
        ),
    )
    object.__setattr__(entity, "_device", device)
    object.__setattr__(entity, "_embedded_id", "zone")
    object.__setattr__(entity, "_attr_hvac_mode", HVACMode.OFF)
    entity.coordinator = coordinator
    entity._climate_control = MagicMock(
        side_effect=[
            previous_management_point,
            current_management_point,
            current_management_point,
            current_management_point,
        ]
    )
    entity._update_state = MagicMock()

    await entity.async_set_hvac_mode(HVACMode.COOL)

    assert previous_management_point.on_off_mode.value == "off"
    assert previous_management_point.operation_mode.value == "heating"
    assert current_management_point.on_off_mode.value == "on"
    assert current_management_point.operation_mode.value == "cooling"
    assert coordinator.async_update_listeners.call_count == 2


async def test_set_hvac_mode_uses_advertised_native_mode() -> None:
    """Use an advertised native mode instead of a generic Daikin value."""
    entity = object.__new__(DaikinClimate)
    device = MagicMock(id="device")
    coordinator = MagicMock()
    coordinator.async_execute_command = AsyncMock(return_value=True)
    operation_mode = SimpleNamespace(
        value="cooling", settable=True, values=["cooling", "heatingNight"]
    )
    climate_control = SimpleNamespace(
        on_off_mode=SimpleNamespace(value="on", settable=True),
        operation_mode=operation_mode,
    )
    object.__setattr__(entity, "_device", device)
    object.__setattr__(entity, "_embedded_id", "zone")
    object.__setattr__(entity, "_attr_hvac_mode", HVACMode.COOL)
    entity.coordinator = coordinator
    entity._climate_control = MagicMock(return_value=climate_control)
    entity._update_state = MagicMock()

    await entity.async_set_hvac_mode(HVACMode.HEAT)

    (await _replay_command(coordinator)).assert_awaited_once_with(
        "device", "zone", "operationMode", "heatingNight", path=None
    )
    assert operation_mode.value == "heatingNight"


async def test_set_hvac_mode_rejects_unknown_native_mode() -> None:
    """Reject a mode without a Home Assistant equivalent before writing power."""
    entity = object.__new__(DaikinClimate)
    device = MagicMock(id="device")
    coordinator = MagicMock()
    coordinator.async_execute_command = AsyncMock()
    operation_mode = SimpleNamespace(
        value="vendorMode", settable=True, values=["vendorMode"]
    )
    climate_control = SimpleNamespace(
        on_off_mode=SimpleNamespace(value="on", settable=True),
        operation_mode=operation_mode,
    )
    object.__setattr__(entity, "_device", device)
    object.__setattr__(entity, "_embedded_id", "zone")
    object.__setattr__(entity, "_setpoint", "roomTemperature")
    object.__setattr__(entity, "_attr_hvac_mode", None)
    entity.coordinator = coordinator
    entity._climate_control = MagicMock(return_value=climate_control)

    with pytest.raises(ServiceValidationError) as err:
        await entity.async_set_hvac_mode(HVACMode.HEAT)

    assert err.value.translation_key == "climate_hvac_mode_unavailable"
    assert entity._get_hvac_mode() is None
    assert entity._get_hvac_modes() == [HVACMode.OFF]
    coordinator.async_execute_command.assert_not_awaited()


def test_missing_power_characteristic_uses_operation_mode() -> None:
    """Treat a climate control without on/off state as powered on."""
    entity = object.__new__(DaikinClimate)
    operation_mode = SimpleNamespace(value="auto")
    entity._climate_control = MagicMock(
        return_value=SimpleNamespace(on_off_mode=None, operation_mode=operation_mode)
    )

    assert entity._get_hvac_mode() is HVACMode.HEAT_COOL


@pytest.mark.parametrize("power_value", [None, "unknown"])
def test_unknown_power_characteristic_uses_unknown_hvac_mode(
    power_value: str | None,
) -> None:
    """Preserve an omitted or invalid power value as an unknown HVAC state."""
    entity = object.__new__(DaikinClimate)
    operation_mode = SimpleNamespace(value="heating")
    entity._climate_control = MagicMock(
        return_value=SimpleNamespace(
            on_off_mode=SimpleNamespace(value=power_value),
            operation_mode=operation_mode,
        )
    )

    assert entity._get_hvac_mode() is None


@pytest.mark.parametrize(
    "operation_mode",
    [None, SimpleNamespace(value=None)],
    ids=["missing", "omitted"],
)
def test_powered_on_without_operation_mode_uses_unknown_hvac_mode(
    operation_mode: object | None,
) -> None:
    """Do not report an explicitly powered-on unit as off without its mode."""
    entity = object.__new__(DaikinClimate)
    entity._climate_control = MagicMock(
        return_value=SimpleNamespace(
            on_off_mode=SimpleNamespace(value="on"),
            operation_mode=operation_mode,
        )
    )

    assert entity._get_hvac_mode() is None


def test_omitted_fixed_fan_speed_uses_unknown_fan_mode() -> None:
    """Do not expose an omitted fixed speed as the string None."""
    entity = object.__new__(DaikinClimate)
    entity._fan_operation = MagicMock(
        return_value=SimpleNamespace(
            fan_speed=SimpleNamespace(
                current_mode=SimpleNamespace(value=FANMODE_FIXED),
                modes={FANMODE_FIXED: SimpleNamespace(value=None)},
            )
        )
    )

    assert entity._get_fan_mode() is None


@pytest.mark.parametrize("direction", ["vertical", "horizontal"])
def test_omitted_swing_value_uses_unknown_mode(direction: str) -> None:
    """Do not lowercase an omitted swing value during a coordinator update."""
    entity = object.__new__(DaikinClimate)
    axis = SimpleNamespace(current_mode=SimpleNamespace(value=None))
    entity._fan_operation = MagicMock(
        return_value=SimpleNamespace(
            fan_direction=SimpleNamespace(vertical=axis, horizontal=axis)
        )
    )

    assert entity._get_swing_mode_for_direction(direction) is None


@pytest.mark.parametrize("direction", ["vertical", "horizontal"])
@pytest.mark.parametrize("missing", ["operation", "direction", "axis"])
def test_missing_swing_axis_uses_unknown_mode(direction: str, missing: str) -> None:
    """Do not expose an empty string when a swing axis is absent."""
    entity = object.__new__(DaikinClimate)
    if missing == "operation":
        entity._fan_operation = MagicMock(return_value=None)
    elif missing == "direction":
        entity._fan_operation = MagicMock(
            return_value=SimpleNamespace(fan_direction=None)
        )
    else:
        entity._fan_operation = MagicMock(
            return_value=SimpleNamespace(
                fan_direction=SimpleNamespace(vertical=None, horizontal=None)
            )
        )

    assert entity._get_swing_mode_for_direction(direction) is None


@pytest.mark.parametrize("power_settable", [False, None])
def test_hvac_modes_exclude_off_without_writable_power(
    power_settable: bool | None,
) -> None:
    """Do not offer an unsupported off mode without writable power control."""
    entity = object.__new__(DaikinClimate)
    on_off_mode = (
        SimpleNamespace(value="on", settable=power_settable)
        if power_settable is not None
        else None
    )
    entity._climate_control = MagicMock(
        return_value=SimpleNamespace(
            on_off_mode=on_off_mode,
            operation_mode=SimpleNamespace(
                value="heating", settable=False, values=["heating"]
            ),
        )
    )

    assert entity._get_hvac_modes() == [HVACMode.HEAT]


def test_observed_off_state_is_advertised_without_writable_power() -> None:
    """Advertise the observed off state even when power control is read-only."""
    entity = object.__new__(DaikinClimate)
    entity._climate_control = MagicMock(
        return_value=SimpleNamespace(
            on_off_mode=SimpleNamespace(value="off", settable=False),
            operation_mode=SimpleNamespace(
                value="heating", settable=False, values=["heating"]
            ),
        )
    )

    assert entity._get_hvac_mode() is HVACMode.OFF
    assert entity._get_hvac_modes() == [HVACMode.OFF, HVACMode.HEAT]


async def test_set_fan_mode_publishes_successful_fixed_mode_write() -> None:
    """Publish fixed mode when the following fan-speed write fails."""
    entity = object.__new__(DaikinClimate)
    device = MagicMock(id="device")
    device.name = "Device"
    coordinator = MagicMock()
    coordinator.async_execute_command = AsyncMock(side_effect=[True, False])
    fan_speed = SimpleNamespace(
        current_mode=SimpleNamespace(settable=True, value="auto"),
        modes={FANMODE_FIXED: SimpleNamespace(value=1, settable=True)},
    )
    climate_control = SimpleNamespace(operation_mode=SimpleNamespace(value="heating"))
    object.__setattr__(entity, "_device", device)
    object.__setattr__(entity, "_embedded_id", "zone")
    entity.coordinator = coordinator
    entity._fan_operation = MagicMock(return_value=SimpleNamespace(fan_speed=fan_speed))
    entity._climate_control = MagicMock(return_value=climate_control)
    entity._get_fan_modes = MagicMock(return_value=["3"])
    entity._get_fan_mode = MagicMock(return_value="1")

    with pytest.raises(HomeAssistantError) as err:
        await entity.async_set_fan_mode("3")

    assert err.value.translation_key == "set_fan_mode_failed"

    assert fan_speed.current_mode.value == FANMODE_FIXED
    assert fan_speed.modes[FANMODE_FIXED].value == 1
    coordinator.async_update_listeners.assert_called_once_with()


async def test_set_fan_mode_updates_captured_operation_mode() -> None:
    """Update the targeted fan mode when polling replaces the active mode."""
    entity = object.__new__(DaikinClimate)
    device = MagicMock(id="device")
    coordinator = MagicMock()
    coordinator.async_execute_command = AsyncMock(return_value=True)
    previous_fan = SimpleNamespace(
        fan_speed=SimpleNamespace(
            current_mode=SimpleNamespace(settable=True, value="auto"), modes={}
        )
    )
    captured_fan = SimpleNamespace(
        fan_speed=SimpleNamespace(
            current_mode=SimpleNamespace(settable=True, value="auto"), modes={}
        )
    )
    active_fan = SimpleNamespace(
        fan_speed=SimpleNamespace(
            current_mode=SimpleNamespace(settable=True, value="auto"), modes={}
        )
    )
    previous_management_point = SimpleNamespace(
        operation_mode=SimpleNamespace(value="heating"),
    )
    previous_management_point.fan_operation = MagicMock(return_value=previous_fan)
    current_management_point = SimpleNamespace(
        operation_mode=SimpleNamespace(value="cooling"),
    )
    current_management_point.fan_operation = MagicMock(
        side_effect=lambda mode=None: {
            "heating": captured_fan,
            "cooling": active_fan,
        }.get(mode)
    )
    object.__setattr__(entity, "_device", device)
    object.__setattr__(entity, "_embedded_id", "zone")
    entity.coordinator = coordinator
    entity._climate_control = MagicMock(
        side_effect=[
            previous_management_point,
            previous_management_point,
            current_management_point,
        ]
    )
    entity._get_fan_modes = MagicMock(return_value=["quiet"])
    entity._get_fan_mode = MagicMock(return_value="auto")

    await entity.async_set_fan_mode("quiet")

    assert captured_fan.fan_speed.current_mode.value == "quiet"
    assert active_fan.fan_speed.current_mode.value == "auto"
    (await _replay_command(coordinator)).assert_awaited_once_with(
        "device",
        "zone",
        "fanControl",
        "quiet",
        path="/operationModes/heating/fanSpeed/currentMode",
    )


async def test_set_swing_mode_updates_captured_operation_mode() -> None:
    """Update the targeted swing mode when polling replaces the active mode."""
    entity = object.__new__(DaikinClimate)
    device = MagicMock(id="device")
    coordinator = MagicMock()
    coordinator.async_execute_command = AsyncMock(return_value=True)
    previous_fan = SimpleNamespace(
        fan_direction=SimpleNamespace(
            vertical=SimpleNamespace(
                current_mode=SimpleNamespace(
                    settable=True, value="stop", values=["stop", "swing"]
                )
            )
        )
    )
    captured_fan = SimpleNamespace(
        fan_direction=SimpleNamespace(
            vertical=SimpleNamespace(
                current_mode=SimpleNamespace(
                    settable=True, value="stop", values=["stop", "swing"]
                )
            )
        )
    )
    active_fan = SimpleNamespace(
        fan_direction=SimpleNamespace(
            vertical=SimpleNamespace(
                current_mode=SimpleNamespace(
                    settable=True, value="stop", values=["stop", "swing"]
                )
            )
        )
    )
    previous_management_point = SimpleNamespace(
        operation_mode=SimpleNamespace(value="heating"),
    )
    previous_management_point.fan_operation = MagicMock(return_value=previous_fan)
    current_management_point = SimpleNamespace(
        operation_mode=SimpleNamespace(value="cooling"),
    )
    current_management_point.fan_operation = MagicMock(
        side_effect=lambda mode=None: {
            "heating": captured_fan,
            "cooling": active_fan,
        }.get(mode)
    )
    object.__setattr__(entity, "_device", device)
    object.__setattr__(entity, "_embedded_id", "zone")
    entity.coordinator = coordinator
    entity._climate_control = MagicMock(
        side_effect=[
            previous_management_point,
            previous_management_point,
            current_management_point,
        ]
    )

    assert await entity._async_set_swing("vertical", SWING_ON)

    assert captured_fan.fan_direction.vertical.current_mode.value == "swing"
    assert active_fan.fan_direction.vertical.current_mode.value == "stop"
    (await _replay_command(coordinator)).assert_awaited_once_with(
        "device",
        "zone",
        "fanControl",
        "swing",
        path="/operationModes/heating/fanDirection/vertical/currentMode",
    )


async def test_set_preset_mode_stops_after_failed_disable() -> None:
    """Do not enable a replacement preset when disabling the old one fails."""
    entity = object.__new__(DaikinClimate)
    device = MagicMock(name="Device")
    coordinator = MagicMock()
    object.__setattr__(entity, "_device", device)
    object.__setattr__(entity, "_attr_preset_mode", PRESET_BOOST)
    entity.coordinator = coordinator
    entity._update_state = MagicMock()
    entity._async_disable_preset_mode = AsyncMock(return_value=False)
    entity._async_enable_preset_mode = AsyncMock()
    entity._get_preset_modes = MagicMock(return_value=[PRESET_NONE, PRESET_COMFORT])

    with pytest.raises(HomeAssistantError) as err:
        await entity.async_set_preset_mode(PRESET_COMFORT)

    assert err.value.translation_key == "set_preset_mode_failed"

    entity._async_disable_preset_mode.assert_awaited_once_with(PRESET_BOOST)
    entity._async_enable_preset_mode.assert_not_awaited()
    entity._update_state.assert_not_called()
    coordinator.async_update_listeners.assert_not_called()


@pytest.mark.parametrize("power_settable", [False, True])
def test_supported_features_require_writable_controls(power_settable: bool) -> None:
    """Only advertise controls that Daikin reports as writable."""
    entity = object.__new__(DaikinClimate)
    entity._get_setpoint = MagicMock(return_value=None)
    entity._get_preset_modes = MagicMock(return_value=[PRESET_NONE])
    entity._climate_control = MagicMock(
        return_value=SimpleNamespace(
            on_off_mode=SimpleNamespace(settable=power_settable)
        )
    )
    entity._fan_operation = MagicMock(return_value=None)

    features = entity._get_supported_features()

    assert bool(features & ClimateEntityFeature.TURN_ON) is power_settable
    assert bool(features & ClimateEntityFeature.TURN_OFF) is power_settable


def test_preset_modes_start_with_none() -> None:
    """Keep the neutral preset before alphabetically ordered supported presets."""
    entity = object.__new__(DaikinClimate)
    entity._preset_characteristic = MagicMock(
        return_value=SimpleNamespace(settable=True)
    )

    assert entity._get_preset_modes() == [
        PRESET_NONE,
        PRESET_AWAY,
        PRESET_BOOST,
        PRESET_COMFORT,
        PRESET_ECO,
    ]


def test_preset_modes_require_writable_characteristics() -> None:
    """Do not advertise a read-only Daikin preset control."""
    entity = object.__new__(DaikinClimate)
    entity._preset_characteristic = MagicMock(
        return_value=SimpleNamespace(settable=False)
    )

    assert entity._get_preset_modes() == [PRESET_NONE]


def test_get_preset_mode_returns_enabled_away_preset() -> None:
    """Recognize the enabled holiday characteristic as the away preset."""
    entity = object.__new__(DaikinClimate)
    entity._preset_characteristic = MagicMock(
        side_effect=lambda characteristic: (
            SimpleNamespace(value=SimpleNamespace(enabled=True))
            if characteristic == "holidayMode"
            else None
        )
    )

    assert entity._get_preset_mode() == PRESET_AWAY


async def test_set_preset_mode_publishes_successful_disable() -> None:
    """Publish a successful preset disable before a replacement fails."""
    entity = object.__new__(DaikinClimate)
    device = MagicMock(name="Device")
    coordinator = MagicMock()
    object.__setattr__(entity, "_device", device)
    object.__setattr__(entity, "_attr_preset_mode", PRESET_BOOST)
    entity.coordinator = coordinator
    entity._update_state = MagicMock()
    entity._async_disable_preset_mode = AsyncMock(return_value=True)
    entity._async_enable_preset_mode = AsyncMock(return_value=False)
    entity._get_preset_modes = MagicMock(return_value=[PRESET_NONE, PRESET_COMFORT])

    with pytest.raises(HomeAssistantError) as err:
        await entity.async_set_preset_mode(PRESET_COMFORT)

    assert err.value.translation_key == "set_preset_mode_failed"

    entity._async_disable_preset_mode.assert_awaited_once_with(PRESET_BOOST)
    entity._async_enable_preset_mode.assert_awaited_once_with(PRESET_COMFORT)
    entity._update_state.assert_called_once_with()
    coordinator.async_update_listeners.assert_called_once_with()


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
    device.async_update_device_registry.assert_not_called()


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
        (SERVICE_SET_HVAC_MODE, {"hvac_mode": HVACMode.OFF}, "on"),
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
        "minimum_temperature",
        "initial_temperature",
        "expected_temperature",
        "should_write",
    ),
    [
        pytest.param(
            US_CUSTOMARY_SYSTEM,
            76,
            0.5,
            None,
            20,
            24.5,
            True,
            id="fahrenheit-conversion",
        ),
        pytest.param(
            METRIC_SYSTEM, 24.4, 1, None, 20, 24, True, id="whole-step-rounding"
        ),
        pytest.param(
            METRIC_SYSTEM,
            20.1,
            0.1,
            None,
            20,
            20.1,
            True,
            id="decimal-step-rounding",
        ),
        pytest.param(
            METRIC_SYSTEM,
            24.25,
            0.5,
            None,
            20,
            24.5,
            True,
            id="halfway-rounds-up",
        ),
        pytest.param(
            METRIC_SYSTEM,
            10.45,
            0.5,
            10.2,
            20,
            10.7,
            True,
            id="step-anchored-to-native-minimum",
        ),
        pytest.param(
            METRIC_SYSTEM,
            -2.5,
            1,
            -10,
            -4,
            -3,
            True,
            id="negative-halfway-with-native-minimum",
        ),
        pytest.param(
            METRIC_SYSTEM, 24.4, None, None, 20, 24.5, True, id="default-step"
        ),
        pytest.param(METRIC_SYSTEM, 10.4, 3, None, 20, 10, True, id="clamp-to-minimum"),
        pytest.param(
            US_CUSTOMARY_SYSTEM,
            76,
            0.5,
            None,
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
    minimum_temperature: float | None,
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
    setpoint.min_value = minimum_temperature
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
    ("native_mode", "expected_mode"),
    [
        ("stop", SWING_OFF),
        ("swing", SWING_ON),
        ("floorHeatingAirflow", "floorheatingairflow"),
        ("windNice", "windnice"),
    ],
)
def test_swing_modes_translate_standard_values(
    native_mode: str, expected_mode: str
) -> None:
    """Map standard swing values while retaining Daikin's extra airflow directions."""
    entity = object.__new__(DaikinClimate)
    axis = SimpleNamespace(
        current_mode=SimpleNamespace(
            settable=True,
            value=native_mode,
            values=["stop", "swing", "floorHeatingAirflow", "windNice"],
        )
    )
    entity._fan_operation = MagicMock(
        return_value=SimpleNamespace(
            fan_direction=SimpleNamespace(vertical=axis, horizontal=axis)
        )
    )
    assert entity._get_swing_mode() == expected_mode
    assert entity._get_swing_horizontal_mode() == expected_mode
    assert entity._get_swing_modes() == [
        SWING_OFF,
        SWING_ON,
        "floorheatingairflow",
        "windnice",
    ]
    assert entity._get_swing_horizontal_modes() == [
        SWING_OFF,
        SWING_ON,
        "floorheatingairflow",
        "windnice",
    ]


def test_fixed_swing_mode_is_not_treated_as_swing_off() -> None:
    """Keep Daikin's fixed direction mode distinct from swing off."""
    entity = object.__new__(DaikinClimate)
    axis = SimpleNamespace(
        current_mode=SimpleNamespace(
            settable=True,
            value="fixed",
            values=["swing", "fixed"],
        )
    )
    entity._fan_operation = MagicMock(
        return_value=SimpleNamespace(
            fan_direction=SimpleNamespace(vertical=axis, horizontal=None)
        )
    )

    assert entity._get_swing_mode() == "fixed"
    assert entity._get_swing_modes() == [SWING_ON, "fixed"]


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
            {"fan_mode": "auto"},
            ClimateEntityFeature.FAN_MODE,
        ),
        (
            "vertical",
            SERVICE_SET_SWING_MODE,
            {"swing_mode": SWING_ON},
            ClimateEntityFeature.SWING_MODE,
        ),
        (
            "horizontal",
            SERVICE_SET_SWING_HORIZONTAL_MODE,
            {"swing_horizontal_mode": SWING_ON},
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
    assert state.attributes["supported_features"] & feature
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
    assert not state.attributes["supported_features"] & feature
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
def test_fan_modes_respect_writable_characteristics(
    current_mode: str,
    mode_settable: bool,
    speed_settable: bool,
    expected_modes: list[str],
) -> None:
    """Treat mode selection and fixed-speed control as independent capabilities."""
    entity = object.__new__(DaikinClimate)
    fan = SimpleNamespace(
        fan_speed=SimpleNamespace(
            current_mode=SimpleNamespace(
                value=current_mode, values=["quiet", "fixed"], settable=mode_settable
            ),
            modes={
                "fixed": SimpleNamespace(
                    value=1,
                    min_value=1,
                    max_value=2,
                    step_value=1,
                    settable=speed_settable,
                )
            },
        )
    )
    entity._fan_operation = MagicMock(return_value=fan)
    assert entity._get_fan_modes() == expected_modes


@pytest.mark.parametrize(
    ("current_mode", "fixed_value"),
    [(None, 1), (FANMODE_FIXED, None)],
)
def test_get_fan_mode_handles_omitted_values(
    current_mode: str | None, fixed_value: int | None
) -> None:
    """Do not turn omitted fan-mode data into a display string."""
    entity = object.__new__(DaikinClimate)
    modes = (
        {FANMODE_FIXED: SimpleNamespace(value=fixed_value)}
        if current_mode == FANMODE_FIXED
        else {}
    )
    entity._fan_operation = MagicMock(
        return_value=SimpleNamespace(
            fan_speed=SimpleNamespace(
                current_mode=SimpleNamespace(value=current_mode), modes=modes
            )
        )
    )

    assert entity._get_fan_mode() is None


def _make_fan_command_entity(
    fan_operation: SimpleNamespace,
) -> DaikinClimate:
    """Build a minimally initialized climate entity for fan command tests."""
    entity = object.__new__(DaikinClimate)
    device = MagicMock(id="gateway", name="Device")
    object.__setattr__(entity, "_device", device)
    object.__setattr__(entity, "_embedded_id", "zone")
    entity.coordinator = MagicMock()
    entity.coordinator.async_execute_command = AsyncMock(return_value=True)
    entity._fan_operation = MagicMock(return_value=fan_operation)
    entity._climate_control = MagicMock(
        return_value=SimpleNamespace(operation_mode=SimpleNamespace(value="heating"))
    )
    entity._get_fan_modes = MagicMock(return_value=["2", "quiet"])
    entity._get_fan_mode = MagicMock(return_value="2")
    return entity


def _fan_operation(
    current_value: str, *, current_settable: bool = True, fixed_value: int = 1
) -> SimpleNamespace:
    """Create fan data with a writable fixed-speed control."""
    return SimpleNamespace(
        fan_speed=SimpleNamespace(
            current_mode=SimpleNamespace(
                value=current_value, settable=current_settable
            ),
            modes={FANMODE_FIXED: SimpleNamespace(value=fixed_value, settable=True)},
        )
    )


async def test_set_fan_mode_rejects_fixed_speed_without_writable_control() -> None:
    """Reject a numeric fan speed if its fixed-speed control is not writable."""
    fan_operation = _fan_operation("auto")
    fan_operation.fan_speed.modes[FANMODE_FIXED].settable = False
    entity = _make_fan_command_entity(fan_operation)

    with pytest.raises(ServiceValidationError) as err:
        await entity.async_set_fan_mode("2")

    assert err.value.translation_key == "fan_control_unavailable"
    entity.coordinator.async_execute_command.assert_not_awaited()


async def test_set_fan_mode_reports_failed_fixed_mode_write() -> None:
    """Report when the cloud rejects switching to fixed fan mode."""
    entity = _make_fan_command_entity(_fan_operation("auto"))
    entity.coordinator.async_execute_command.return_value = False

    with pytest.raises(HomeAssistantError) as err:
        await entity.async_set_fan_mode("2")

    assert err.value.translation_key == "set_fan_mode_failed"


async def test_set_fan_mode_handles_disappearing_data_after_fixed_mode_write() -> None:
    """Stop safely if a successful mode write is followed by missing state."""
    entity = _make_fan_command_entity(_fan_operation("auto"))
    entity._fan_operation = MagicMock(side_effect=[_fan_operation("auto"), None])

    await entity.async_set_fan_mode("2")

    entity.coordinator.async_execute_command.assert_awaited_once()


async def test_set_fan_mode_handles_disappearing_data_after_speed_write() -> None:
    """Stop safely if updated fan state disappears after setting its speed."""
    entity = _make_fan_command_entity(_fan_operation("auto"))
    entity._fan_operation = MagicMock(
        side_effect=[_fan_operation("auto"), _fan_operation(FANMODE_FIXED), None]
    )

    await entity.async_set_fan_mode("2")

    assert entity.coordinator.async_execute_command.await_count == 2


async def test_set_fan_mode_handles_missing_fixed_speed_after_write() -> None:
    """Stop safely if fixed-speed metadata disappears after the write."""
    entity = _make_fan_command_entity(_fan_operation("auto"))
    updated = _fan_operation(FANMODE_FIXED)
    after_speed_write = _fan_operation(FANMODE_FIXED)
    after_speed_write.fan_speed.modes = {}
    entity._fan_operation = MagicMock(
        side_effect=[_fan_operation("auto"), updated, after_speed_write]
    )

    await entity.async_set_fan_mode("2")

    assert entity.coordinator.async_execute_command.await_count == 2


async def test_set_fan_mode_rejects_read_only_current_mode() -> None:
    """Reject a standard fan-mode write when the characteristic is read-only."""
    entity = _make_fan_command_entity(
        SimpleNamespace(
            fan_speed=SimpleNamespace(
                current_mode=SimpleNamespace(value="auto", settable=False), modes={}
            )
        )
    )

    with pytest.raises(ServiceValidationError) as err:
        await entity.async_set_fan_mode("quiet")

    assert err.value.translation_key == "fan_control_unavailable"
    entity.coordinator.async_execute_command.assert_not_awaited()


async def test_set_fan_mode_reports_failed_standard_mode_write() -> None:
    """Report when the cloud rejects a standard fan-mode write."""
    entity = _make_fan_command_entity(
        SimpleNamespace(
            fan_speed=SimpleNamespace(
                current_mode=SimpleNamespace(value="auto", settable=True), modes={}
            )
        )
    )
    entity.coordinator.async_execute_command.return_value = False

    with pytest.raises(HomeAssistantError) as err:
        await entity.async_set_fan_mode("quiet")

    assert err.value.translation_key == "set_fan_mode_failed"


async def test_set_fan_mode_handles_disappearing_standard_mode_data() -> None:
    """Stop safely if fan data disappears after a standard mode write."""
    entity = _make_fan_command_entity(
        SimpleNamespace(
            fan_speed=SimpleNamespace(
                current_mode=SimpleNamespace(value="auto", settable=True), modes={}
            )
        )
    )
    entity._fan_operation = MagicMock(
        side_effect=[
            SimpleNamespace(
                fan_speed=SimpleNamespace(
                    current_mode=SimpleNamespace(value="auto", settable=True),
                    modes={},
                )
            ),
            None,
        ]
    )

    await entity.async_set_fan_mode("quiet")

    entity.coordinator.async_execute_command.assert_awaited_once()


@pytest.mark.parametrize(
    ("fan_operation", "climate_control"),
    [
        (None, None),
        (SimpleNamespace(fan_direction=None), SimpleNamespace(operation_mode=None)),
    ],
)
async def test_set_swing_returns_false_when_control_data_is_missing(
    fan_operation: SimpleNamespace | None, climate_control: SimpleNamespace | None
) -> None:
    """Return false when swing controls or their operation mode are absent."""
    entity = object.__new__(DaikinClimate)
    entity._fan_operation = MagicMock(return_value=fan_operation)
    entity._climate_control = MagicMock(return_value=climate_control)

    assert not await entity._async_set_swing("vertical", SWING_ON)


@pytest.mark.parametrize(
    "axis",
    [
        None,
        SimpleNamespace(current_mode=SimpleNamespace(settable=False, values=[])),
    ],
)
async def test_set_swing_returns_false_when_axis_is_missing_or_read_only(
    axis: SimpleNamespace | None,
) -> None:
    """Return false when the requested swing axis cannot be written."""
    entity = object.__new__(DaikinClimate)
    entity._fan_operation = MagicMock(
        return_value=SimpleNamespace(fan_direction=SimpleNamespace(vertical=axis))
    )
    entity._climate_control = MagicMock(
        return_value=SimpleNamespace(operation_mode=SimpleNamespace(value="heating"))
    )

    assert not await entity._async_set_swing("vertical", SWING_ON)
