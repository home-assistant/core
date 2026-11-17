"""Tests for Daikin Onecta air purifier fan entities."""

from collections.abc import Awaitable, Callable
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from daikin_onecta.client import OnectaClient
from daikin_onecta.models import Characteristic
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.daikin_onecta.const import FANMODE_FIXED
from homeassistant.components.daikin_onecta.fan import DaikinAirPurifier
from homeassistant.components.fan import (
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_TURN_OFF as FAN_SERVICE_TURN_OFF,
    SERVICE_TURN_ON as FAN_SERVICE_TURN_ON,
    FanEntityCapabilityAttribute,
    FanEntityFeature,
    FanEntityStateAttribute,
    FanServiceArgument,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .platform_helpers import _execute_typed_command
from .test_climate_snapshots import _async_setup_fixture


async def test_air_purifier_speed_updates_captured_mode_after_model_replacement(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """A changed cloud mode does not redirect a pending speed command or its cache."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    coordinator = config_entry.runtime_data
    execute = _execute_typed_command(config_entry)
    coordinator.async_execute_command = execute
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {
            ATTR_ENTITY_ID: "fan.air_purifier_climatecontrol",
            FanServiceArgument.PERCENTAGE: 50,
        },
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
    coordinator.client.patch_characteristic.reset_mock()

    async def replace_model(command: Callable[[OnectaClient], Awaitable[None]]) -> bool:
        device.set_device_data(deepcopy(device.device))
        device.management_point(embedded_id).air_purification.mode.value = "autoFan"
        return await execute(command)

    coordinator.async_execute_command = AsyncMock(side_effect=replace_model)
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {
            ATTR_ENTITY_ID: "fan.air_purifier_climatecontrol",
            FanServiceArgument.PERCENTAGE: 100,
        },
        blocking=True,
    )

    coordinator.client.patch_characteristic.assert_awaited_once_with(
        device.id,
        embedded_id,
        "fanControl",
        4,
        path="/airPurificationModes/manualFan/fanSpeed/modes/fixed",
    )
    purification = device.management_point(embedded_id).air_purification
    assert purification.mode.value == "autoFan"
    assert purification.fan_operation("manualFan").fan_speed.modes["fixed"].value == 4


@pytest.mark.parametrize(
    ("method", "args", "translation_key"),
    [
        ("async_turn_on", (), "air_purifier_power_unavailable"),
        ("async_turn_off", (), "air_purifier_power_unavailable"),
        ("async_set_preset_mode", ("auto_fan",), "air_purifier_mode_unavailable"),
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


async def test_air_purifier_preset_updates_cached_state(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """A successful purifier command updates its native preset state."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    config_entry.runtime_data.async_execute_command = _execute_typed_command(
        config_entry
    )

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {
            ATTR_ENTITY_ID: "fan.air_purifier_climatecontrol",
            FanServiceArgument.PRESET_MODE: "auto_fan",
        },
        blocking=True,
    )

    state = hass.states.get("fan.air_purifier_climatecontrol")
    assert state is not None
    assert state.attributes[FanEntityStateAttribute.PRESET_MODE] == "auto_fan"
    device = next(iter(config_entry.runtime_data.data.values()))
    point = device.device.management_points_by_type("climateControl")[0]
    assert point.air_purification.mode.value == "autoFan"


async def test_air_purifier_percentage_switches_to_manual_and_updates_cache(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Setting speed selects the writable manual mode and updates its cache."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    config_entry.runtime_data.async_execute_command = _execute_typed_command(
        config_entry
    )

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {
            ATTR_ENTITY_ID: "fan.air_purifier_climatecontrol",
            FanServiceArgument.PERCENTAGE: 100,
        },
        blocking=True,
    )

    state = hass.states.get("fan.air_purifier_climatecontrol")
    assert state is not None
    assert state.attributes[FanEntityStateAttribute.PRESET_MODE] is None
    assert (
        "manualFan" not in state.attributes[FanEntityCapabilityAttribute.PRESET_MODES]
    )
    assert state.attributes[FanEntityStateAttribute.PERCENTAGE] == 100


async def test_air_purifier_uses_discrete_speed_percentages(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Map purifier percentages to the finite native speed list."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    coordinator = config_entry.runtime_data
    coordinator.async_execute_command = _execute_typed_command(config_entry)
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {
            ATTR_ENTITY_ID: "fan.air_purifier_climatecontrol",
            FanServiceArgument.PERCENTAGE: 100,
        },
        blocking=True,
    )
    coordinator.client.patch_characteristic.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {
            ATTR_ENTITY_ID: "fan.air_purifier_climatecontrol",
            FanServiceArgument.PERCENTAGE: 25,
        },
        blocking=True,
    )

    coordinator.client.patch_characteristic.assert_awaited_once()
    assert coordinator.client.patch_characteristic.await_args.args[3] == 1
    assert (
        hass.states.get("fan.air_purifier_climatecontrol").attributes[
            FanEntityStateAttribute.PERCENTAGE
        ]
        == 25
    )


def test_air_purifier_preserves_unknown_power_state() -> None:
    """Do not interpret an omitted purifier power value as off."""
    entity = object.__new__(DaikinAirPurifier)
    purification = SimpleNamespace(
        power=Characteristic(value=None, settable=True),
        mode=None,
        modes=[],
        fan_operation=MagicMock(return_value=None),
    )
    entity._air_purification = MagicMock(return_value=purification)

    entity._update_state()

    assert entity.is_on is None
    assert entity.percentage is None


def test_air_purifier_preserves_unknown_fixed_speed() -> None:
    """Do not convert an omitted native fixed speed to an integer."""
    entity = object.__new__(DaikinAirPurifier)
    operation = SimpleNamespace(
        fan_speed=SimpleNamespace(
            modes={FANMODE_FIXED: Characteristic(value=None, settable=True)}
        )
    )
    purification = SimpleNamespace(
        power=Characteristic(value="on", settable=True),
        mode=Characteristic(value="manualFan", settable=True),
        modes=["manualFan"],
        fan_operation=MagicMock(return_value=operation),
    )
    entity._air_purification = MagicMock(return_value=purification)
    entity._fixed_speeds = MagicMock(return_value=[1, 2, 3, 4])
    entity._fixed_speed_count = MagicMock(return_value=4)

    entity._update_state()

    assert entity.percentage is None


@pytest.mark.parametrize("method", ["async_turn_on", "async_turn_off"])
async def test_air_purifier_rejects_unknown_power_state(method: str) -> None:
    """Reject purifier commands when Daikin omits the current power value."""
    entity = object.__new__(DaikinAirPurifier)
    object.__setattr__(entity, "_device", MagicMock(name="Device"))
    entity._air_purification = MagicMock(
        return_value=SimpleNamespace(power=Characteristic(value=None, settable=True))
    )
    entity._power_control_is_available = MagicMock(return_value=True)
    entity._async_execute_air_purification_command = AsyncMock()

    with pytest.raises(ServiceValidationError) as err:
        await getattr(entity, method)()

    assert err.value.translation_key == "air_purifier_power_unavailable"
    entity._async_execute_air_purification_command.assert_not_awaited()


async def test_air_purifier_percentage_rejects_unknown_power_before_mode_write() -> (
    None
):
    """Do not partially change purifier mode when its power state is unknown."""
    entity = object.__new__(DaikinAirPurifier)
    object.__setattr__(entity, "_device", MagicMock(name="Device"))
    object.__setattr__(entity, "_attr_is_on", None)
    entity._air_purification = MagicMock(
        return_value=SimpleNamespace(
            power=Characteristic(value=None, settable=True),
            mode=Characteristic(value="autoFan"),
        )
    )
    entity._async_set_mode = AsyncMock()

    with pytest.raises(ServiceValidationError) as err:
        await entity.async_set_percentage(100)

    assert err.value.translation_key == "air_purifier_power_unavailable"
    entity._async_set_mode.assert_not_awaited()


async def test_air_purifier_turn_off_then_on_updates_cached_state(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Power commands immediately publish their successful local state."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    config_entry.runtime_data.async_execute_command = _execute_typed_command(
        config_entry
    )

    await hass.services.async_call(
        FAN_DOMAIN,
        FAN_SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "fan.air_purifier_climatecontrol"},
        blocking=True,
    )
    state = hass.states.get("fan.air_purifier_climatecontrol")
    assert state is not None
    assert state.state == "off"
    assert state.attributes[FanEntityStateAttribute.PERCENTAGE] == 0

    await hass.services.async_call(
        FAN_DOMAIN,
        FAN_SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "fan.air_purifier_climatecontrol"},
        blocking=True,
    )
    state = hass.states.get("fan.air_purifier_climatecontrol")
    assert state is not None
    assert state.state == "on"


async def test_air_purifier_ignores_unchanged_preset(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Do not spend a cloud request when the selected purifier mode is unchanged."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    execute_command = _execute_typed_command(config_entry)
    config_entry.runtime_data.async_execute_command = execute_command

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {
            ATTR_ENTITY_ID: "fan.air_purifier_climatecontrol",
            FanServiceArgument.PRESET_MODE: "econo",
        },
        blocking=True,
    )

    execute_command.assert_not_awaited()


async def test_air_purifier_percentage_turns_on_and_exits_preset(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """A nonzero manual speed powers on an off purifier and clears its preset."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    config_entry.runtime_data.async_execute_command = _execute_typed_command(
        config_entry
    )
    await hass.services.async_call(
        FAN_DOMAIN,
        FAN_SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "fan.air_purifier_climatecontrol"},
        blocking=True,
    )
    assert (
        hass.states.get("fan.air_purifier_climatecontrol").attributes[
            FanEntityStateAttribute.PERCENTAGE
        ]
        == 0
    )

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {
            ATTR_ENTITY_ID: "fan.air_purifier_climatecontrol",
            FanServiceArgument.PERCENTAGE: 100,
        },
        blocking=True,
    )
    state = hass.states.get("fan.air_purifier_climatecontrol")
    assert state is not None
    assert state.state == "on"
    assert state.attributes[FanEntityStateAttribute.PRESET_MODE] is None
    assert state.attributes[FanEntityStateAttribute.PERCENTAGE] == 100


async def test_air_purifier_rejects_manual_speed_as_preset(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """The HA preset action must not expose the native manual speed mode."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    command = _execute_typed_command(config_entry)
    config_entry.runtime_data.async_execute_command = command

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {
                ATTR_ENTITY_ID: "fan.air_purifier_climatecontrol",
                FanServiceArgument.PRESET_MODE: "manualFan",
            },
            blocking=True,
        )

    command.assert_not_awaited()


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


@pytest.mark.parametrize(
    ("mode", "fixed", "expected"),
    [
        ("missing", None, []),
        ("read_only", SimpleNamespace(settable=False), []),
        (
            "missing_bounds",
            SimpleNamespace(settable=True, min_value=1, max_value=None, step_value=1),
            [],
        ),
        (
            "missing_step",
            SimpleNamespace(settable=True, min_value=1, max_value=3, step_value=None),
            [],
        ),
        (
            "invalid_step",
            SimpleNamespace(settable=True, min_value=1, max_value=3, step_value=0),
            [],
        ),
        (
            "fractional_bounds",
            SimpleNamespace(settable=True, min_value=1.5, max_value=3, step_value=1),
            [],
        ),
        (
            "fractional_step",
            SimpleNamespace(settable=True, min_value=1, max_value=3, step_value=0.5),
            [],
        ),
        (
            "valid",
            SimpleNamespace(settable=True, min_value=1, max_value=5, step_value=2),
            [1, 3, 5],
        ),
    ],
)
def test_air_purifier_fixed_speeds(
    mode: str, fixed: object, expected: list[int]
) -> None:
    """Only expose integral, writable fixed speeds."""
    entity = object.__new__(DaikinAirPurifier)
    operation = SimpleNamespace(
        fan_speed=SimpleNamespace(modes={FANMODE_FIXED: fixed} if fixed else None)
    )
    purification = SimpleNamespace(
        fan_operation=MagicMock(return_value=operation if mode != "missing" else None)
    )
    entity._air_purification = MagicMock(return_value=purification)

    assert entity._fixed_speeds() == expected
    assert entity._fixed_speed_count() == (len(expected) or None)


async def test_air_purifier_turn_on_applies_optional_controls() -> None:
    """Apply requested preset and speed after an already-on power state."""
    entity = object.__new__(DaikinAirPurifier)
    entity._air_purification = MagicMock(
        return_value=SimpleNamespace(power=SimpleNamespace(value="on", settable=True))
    )
    entity.async_set_preset_mode = AsyncMock()
    entity.async_set_percentage = AsyncMock()

    await entity.async_turn_on(percentage=65, preset_mode="auto_fan")

    entity.async_set_preset_mode.assert_awaited_once_with("auto_fan")
    entity.async_set_percentage.assert_awaited_once_with(65)


async def test_air_purifier_turn_off_is_noop_when_already_off() -> None:
    """Avoid a cloud write when the purifier is already off."""
    entity = object.__new__(DaikinAirPurifier)
    entity._air_purification = MagicMock(
        return_value=SimpleNamespace(power=SimpleNamespace(value="off", settable=True))
    )
    entity._async_execute_air_purification_command = AsyncMock()

    await entity.async_turn_off()

    entity._async_execute_air_purification_command.assert_not_awaited()


async def test_air_purifier_zero_percentage_turns_off() -> None:
    """Map zero fan percentage to the fan turn-off operation."""
    entity = object.__new__(DaikinAirPurifier)
    entity.async_turn_off = AsyncMock()

    await entity.async_set_percentage(0)

    entity.async_turn_off.assert_awaited_once_with()


async def test_air_purifier_percentage_rejects_missing_speed_after_mode_change() -> (
    None
):
    """Reject a speed command if selecting manual mode removes the mode data."""
    entity = object.__new__(DaikinAirPurifier)
    mode = SimpleNamespace(value="autoFan", settable=True)
    purification = SimpleNamespace(
        mode=mode,
        modes=["autoFan", "manualFan"],
        power=SimpleNamespace(value="on", settable=True),
    )
    entity._air_purification = MagicMock(side_effect=[purification, purification, None])
    entity._fixed_speeds = MagicMock(return_value=[1, 2, 3])
    entity._async_set_mode = AsyncMock()
    entity._attr_is_on = True
    entity._device = SimpleNamespace(name="Purifier")

    with pytest.raises(ServiceValidationError) as err:
        await entity.async_set_percentage(50)

    assert err.value.translation_key == "air_purifier_speed_unavailable"


async def test_air_purifier_percentage_rejects_unsupported_fixed_speeds() -> None:
    """Reject a manual-mode request when Daikin exposes no writable speeds."""
    entity = object.__new__(DaikinAirPurifier)
    purification = SimpleNamespace(
        mode=SimpleNamespace(value="manualFan", settable=True),
        power=SimpleNamespace(value="on", settable=True),
    )
    entity._air_purification = MagicMock(return_value=purification)
    entity._fixed_speeds = MagicMock(return_value=[])
    entity._device = SimpleNamespace(name="Purifier")

    with pytest.raises(ServiceValidationError) as err:
        await entity.async_set_percentage(50)

    assert err.value.translation_key == "air_purifier_speed_unavailable"
