"""Tests for Daikin Onecta air purifier fan entities."""

from collections.abc import Awaitable, Callable
from copy import deepcopy
from unittest.mock import AsyncMock, patch

from daikin_onecta.client import OnectaClient
from daikin_onecta.models import ManagementPoint
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
from homeassistant.const import ATTR_ENTITY_ID, ATTR_SUPPORTED_FEATURES
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .conftest import MockOnectaClient
from .platform_helpers import (
    AIR_PURIFIER_ENTITY_ID,
    _async_setup_fixture,
    _execute_typed_command,
)


def _air_purification(config_entry: MockConfigEntry):
    """Return the purifier state from the loaded fixture gateway."""
    device = next(iter(config_entry.runtime_data.data.values()))
    point = device.device.management_points_by_type("climateControl")[0]
    assert point.air_purification is not None
    return point.air_purification


async def test_air_purifier_speed_updates_captured_mode_after_model_replacement(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """A changed cloud mode does not redirect a pending speed command or its cache."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    coordinator = config_entry.runtime_data
    execute = _execute_typed_command(config_entry, mock_onecta_client)
    coordinator.async_execute_command = execute
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {
            ATTR_ENTITY_ID: AIR_PURIFIER_ENTITY_ID,
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
    mock_onecta_client.patch_characteristic.reset_mock()

    async def replace_model(command: Callable[[OnectaClient], Awaitable[None]]) -> bool:
        device.set_device_data(deepcopy(device.device))
        device.management_point(embedded_id).air_purification.mode.value = "autoFan"
        return await execute(command)

    coordinator.async_execute_command = AsyncMock(side_effect=replace_model)
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {
            ATTR_ENTITY_ID: AIR_PURIFIER_ENTITY_ID,
            FanServiceArgument.PERCENTAGE: 100,
        },
        blocking=True,
    )

    mock_onecta_client.patch_characteristic.assert_awaited_once_with(
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
    "fixed_speed",
    [pytest.param(0, id="below-range"), pytest.param(2.5, id="fractional")],
)
async def test_air_purifier_ignores_unknown_fixed_speed(
    hass: HomeAssistant, config_entry: MockConfigEntry, fixed_speed: float
) -> None:
    """Keep the fan platform available when Daikin reports an invalid speed."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    coordinator = config_entry.runtime_data
    purification = _air_purification(config_entry)
    purification.mode.value = "manualFan"
    operation = purification.fan_operation("manualFan")
    assert operation is not None
    assert operation.fan_speed is not None
    assert operation.fan_speed.modes is not None
    operation.fan_speed.modes[FANMODE_FIXED].value = fixed_speed

    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    state = hass.states.get(AIR_PURIFIER_ENTITY_ID)
    assert state is not None
    assert state.attributes[FanEntityStateAttribute.PERCENTAGE] is None


def _make_purifier_mode_read_only(point: ManagementPoint) -> None:
    """Make purifier mode selection unavailable while preserving power control."""
    assert point.air_purification is not None
    assert point.air_purification.mode is not None
    point.air_purification.mode.settable = False


def _remove_purifier_fixed_speed(point: ManagementPoint) -> None:
    """Remove the manual fixed-speed control while preserving power control."""
    assert point.air_purification is not None
    operation = point.air_purification.fan_operation("manualFan")
    assert operation is not None
    assert operation.fan_speed is not None
    assert operation.fan_speed.modes is not None
    operation.fan_speed.modes.pop(FANMODE_FIXED)


@pytest.mark.parametrize(
    ("service", "service_data", "make_unavailable", "translation_key"),
    [
        pytest.param(
            SERVICE_SET_PRESET_MODE,
            {FanServiceArgument.PRESET_MODE: "auto_fan"},
            _make_purifier_mode_read_only,
            "air_purifier_mode_unavailable",
            id="mode",
        ),
        pytest.param(
            SERVICE_SET_PERCENTAGE,
            {FanServiceArgument.PERCENTAGE: 50},
            _remove_purifier_fixed_speed,
            "air_purifier_speed_unavailable",
            id="speed",
        ),
    ],
)
async def test_air_purifier_rejects_unavailable_controls(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    service: str,
    service_data: dict[str, str | int],
    make_unavailable: Callable[[ManagementPoint], None],
    translation_key: str,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Reject purifier services when the cloud no longer provides its controls."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    coordinator = config_entry.runtime_data
    execute = _execute_typed_command(config_entry, mock_onecta_client)
    coordinator.async_execute_command = execute
    point = next(iter(coordinator.data.values())).device.management_points_by_type(
        "climateControl"
    )[0]
    make_unavailable(point)
    state = hass.states.get(AIR_PURIFIER_ENTITY_ID)
    assert state is not None and state.state != "unavailable"
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            FAN_DOMAIN,
            service,
            {ATTR_ENTITY_ID: AIR_PURIFIER_ENTITY_ID, **service_data},
            blocking=True,
        )

    assert err.value.translation_key == translation_key
    execute.assert_not_awaited()


async def test_air_purifier_preset_updates_cached_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """A successful purifier command updates its native preset state."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    config_entry.runtime_data.async_execute_command = _execute_typed_command(
        config_entry, mock_onecta_client
    )

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {
            ATTR_ENTITY_ID: AIR_PURIFIER_ENTITY_ID,
            FanServiceArgument.PRESET_MODE: "auto_fan",
        },
        blocking=True,
    )

    state = hass.states.get(AIR_PURIFIER_ENTITY_ID)
    assert state is not None
    assert state.attributes[FanEntityStateAttribute.PRESET_MODE] == "auto_fan"
    device = next(iter(config_entry.runtime_data.data.values()))
    point = device.device.management_points_by_type("climateControl")[0]
    assert point.air_purification.mode.value == "autoFan"


async def test_air_purifier_percentage_switches_to_manual_and_updates_cache(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Setting speed selects the writable manual mode and updates its cache."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    config_entry.runtime_data.async_execute_command = _execute_typed_command(
        config_entry, mock_onecta_client
    )

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {
            ATTR_ENTITY_ID: AIR_PURIFIER_ENTITY_ID,
            FanServiceArgument.PERCENTAGE: 100,
        },
        blocking=True,
    )

    state = hass.states.get(AIR_PURIFIER_ENTITY_ID)
    assert state is not None
    assert state.attributes[FanEntityStateAttribute.PRESET_MODE] is None
    assert (
        "manualFan" not in state.attributes[FanEntityCapabilityAttribute.PRESET_MODES]
    )
    assert state.attributes[FanEntityStateAttribute.PERCENTAGE] == 100


async def test_air_purifier_uses_discrete_speed_percentages(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Map purifier percentages to the finite native speed list."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    coordinator = config_entry.runtime_data
    coordinator.async_execute_command = _execute_typed_command(
        config_entry, mock_onecta_client
    )
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {
            ATTR_ENTITY_ID: AIR_PURIFIER_ENTITY_ID,
            FanServiceArgument.PERCENTAGE: 100,
        },
        blocking=True,
    )
    mock_onecta_client.patch_characteristic.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {
            ATTR_ENTITY_ID: AIR_PURIFIER_ENTITY_ID,
            FanServiceArgument.PERCENTAGE: 25,
        },
        blocking=True,
    )

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {
            ATTR_ENTITY_ID: AIR_PURIFIER_ENTITY_ID,
            FanServiceArgument.PERCENTAGE: 24,
        },
        blocking=True,
    )

    mock_onecta_client.patch_characteristic.assert_awaited_once()
    assert mock_onecta_client.patch_characteristic.await_args.args[3] == 1
    assert (
        hass.states.get(AIR_PURIFIER_ENTITY_ID).attributes[
            FanEntityStateAttribute.PERCENTAGE
        ]
        == 25
    )


async def test_air_purifier_preserves_unknown_power_state(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Do not interpret an omitted cloud power value as off in HA state."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    purification = _air_purification(config_entry)
    assert purification.power is not None
    purification.power.value = None
    config_entry.runtime_data.async_update_listeners()
    await hass.async_block_till_done()

    state = hass.states.get(AIR_PURIFIER_ENTITY_ID)
    assert state is not None
    assert state.state == "unknown"
    assert state.attributes[FanEntityStateAttribute.PERCENTAGE] is None


async def test_air_purifier_preserves_unknown_fixed_speed(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Do not publish a percentage when the cloud omits fixed speed value."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    purification = _air_purification(config_entry)
    assert purification.mode is not None
    purification.mode.value = "manualFan"
    operation = purification.fan_operation("manualFan")
    assert operation is not None and operation.fan_speed is not None
    assert operation.fan_speed.modes is not None
    operation.fan_speed.modes[FANMODE_FIXED].value = None
    config_entry.runtime_data.async_update_listeners()
    await hass.async_block_till_done()

    state = hass.states.get(AIR_PURIFIER_ENTITY_ID)
    assert state is not None
    assert state.attributes[FanEntityStateAttribute.PERCENTAGE] is None


@pytest.mark.parametrize("service", [FAN_SERVICE_TURN_ON, FAN_SERVICE_TURN_OFF])
async def test_air_purifier_rejects_unknown_power_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    service: str,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Reject HA power services when Daikin omits its current value."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    coordinator = config_entry.runtime_data
    execute = _execute_typed_command(config_entry, mock_onecta_client)
    coordinator.async_execute_command = execute
    purification = _air_purification(config_entry)
    assert purification.power is not None
    purification.power.value = None
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            FAN_DOMAIN,
            service,
            {ATTR_ENTITY_ID: AIR_PURIFIER_ENTITY_ID},
            blocking=True,
        )

    assert err.value.translation_key == "air_purifier_power_unavailable"
    execute.assert_not_awaited()


async def test_air_purifier_percentage_rejects_unknown_power_before_mode_write(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Do not change purifier mode through HA when its power state is unknown."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    coordinator = config_entry.runtime_data
    execute = _execute_typed_command(config_entry, mock_onecta_client)
    coordinator.async_execute_command = execute
    purification = _air_purification(config_entry)
    assert purification.power is not None
    purification.power.value = None
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PERCENTAGE,
            {
                ATTR_ENTITY_ID: AIR_PURIFIER_ENTITY_ID,
                FanServiceArgument.PERCENTAGE: 100,
            },
            blocking=True,
        )

    assert err.value.translation_key == "air_purifier_power_unavailable"
    execute.assert_not_awaited()


async def test_air_purifier_turn_off_then_on_updates_cached_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Power commands immediately publish their successful local state."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    config_entry.runtime_data.async_execute_command = _execute_typed_command(
        config_entry, mock_onecta_client
    )

    await hass.services.async_call(
        FAN_DOMAIN,
        FAN_SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: AIR_PURIFIER_ENTITY_ID},
        blocking=True,
    )
    state = hass.states.get(AIR_PURIFIER_ENTITY_ID)
    assert state is not None
    assert state.state == "off"
    assert state.attributes[FanEntityStateAttribute.PERCENTAGE] == 0

    await hass.services.async_call(
        FAN_DOMAIN,
        FAN_SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: AIR_PURIFIER_ENTITY_ID},
        blocking=True,
    )
    state = hass.states.get(AIR_PURIFIER_ENTITY_ID)
    assert state is not None
    assert state.state == "on"


async def test_air_purifier_turn_on_rejects_invalid_preset_before_power_write(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Validate a requested preset before turning on the purifier."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    execute = _execute_typed_command(config_entry, mock_onecta_client)
    config_entry.runtime_data.async_execute_command = execute
    purification = _air_purification(config_entry)
    assert purification.power is not None
    purification.power.value = "off"
    config_entry.runtime_data.async_update_listeners()
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            FAN_DOMAIN,
            FAN_SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: AIR_PURIFIER_ENTITY_ID,
                FanServiceArgument.PRESET_MODE: "not_a_preset",
            },
            blocking=True,
        )

    assert err.value.translation_key == "not_valid_preset_mode"
    execute.assert_not_awaited()
    assert purification.power.value == "off"


async def test_air_purifier_ignores_unchanged_preset(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Do not spend a cloud request when the selected purifier mode is unchanged."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    execute_command = _execute_typed_command(config_entry, mock_onecta_client)
    config_entry.runtime_data.async_execute_command = execute_command

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {
            ATTR_ENTITY_ID: AIR_PURIFIER_ENTITY_ID,
            FanServiceArgument.PRESET_MODE: "econo",
        },
        blocking=True,
    )

    execute_command.assert_not_awaited()


async def test_air_purifier_percentage_turns_on_and_exits_preset(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """A nonzero manual speed powers on an off purifier and clears its preset."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    config_entry.runtime_data.async_execute_command = _execute_typed_command(
        config_entry, mock_onecta_client
    )
    await hass.services.async_call(
        FAN_DOMAIN,
        FAN_SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: AIR_PURIFIER_ENTITY_ID},
        blocking=True,
    )
    assert (
        hass.states.get(AIR_PURIFIER_ENTITY_ID).attributes[
            FanEntityStateAttribute.PERCENTAGE
        ]
        == 0
    )

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {
            ATTR_ENTITY_ID: AIR_PURIFIER_ENTITY_ID,
            FanServiceArgument.PERCENTAGE: 100,
        },
        blocking=True,
    )
    state = hass.states.get(AIR_PURIFIER_ENTITY_ID)
    assert state is not None
    assert state.state == "on"
    assert state.attributes[FanEntityStateAttribute.PRESET_MODE] is None
    assert state.attributes[FanEntityStateAttribute.PERCENTAGE] == 100


async def test_air_purifier_percentage_powers_on_before_mode_and_speed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Power on an off purifier before changing its mode and fan speed."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    coordinator = config_entry.runtime_data
    coordinator.async_execute_command = _execute_typed_command(
        config_entry, mock_onecta_client
    )
    await hass.services.async_call(
        FAN_DOMAIN,
        FAN_SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: AIR_PURIFIER_ENTITY_ID},
        blocking=True,
    )
    mock_onecta_client.patch_characteristic.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {
            ATTR_ENTITY_ID: AIR_PURIFIER_ENTITY_ID,
            FanServiceArgument.PERCENTAGE: 50,
        },
        blocking=True,
    )

    device = next(iter(coordinator.data.values()))
    point = device.device.management_points_by_type("climateControl")[0]
    assert mock_onecta_client.patch_characteristic.await_args_list == [
        ((device.id, point.embedded_id, "onOffMode", "on"), {"path": None}),
        (
            (device.id, point.embedded_id, "airPurificationMode", "manualFan"),
            {"path": None},
        ),
        (
            (device.id, point.embedded_id, "fanControl", 2),
            {"path": "/airPurificationModes/manualFan/fanSpeed/modes/fixed"},
        ),
    ]


async def test_air_purifier_percentage_uses_replaced_model_after_turn_on(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Re-read purifier state after turning it on replaces the cached model."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    coordinator = config_entry.runtime_data
    device = next(iter(coordinator.data.values()))
    entity = hass.data[FAN_DOMAIN].get_entity(AIR_PURIFIER_ENTITY_ID)
    assert isinstance(entity, DaikinAirPurifier)
    old_purification = _air_purification(config_entry)
    assert old_purification.power is not None and old_purification.mode is not None
    old_purification.power.value = "off"
    old_purification.mode.value = "autoFan"
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    replacement = deepcopy(device.device)
    replacement_point = replacement.management_points_by_type("climateControl")[0]
    assert replacement_point.air_purification is not None
    assert replacement_point.air_purification.power is not None
    assert replacement_point.air_purification.mode is not None
    replacement_point.air_purification.power.value = "on"
    replacement_point.air_purification.mode.value = "manualFan"
    coordinator.async_execute_command = _execute_typed_command(
        config_entry, mock_onecta_client
    )

    async def replace_model() -> None:
        device.set_device_data(replacement)

    with patch.object(entity, "async_turn_on", side_effect=replace_model):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PERCENTAGE,
            {
                ATTR_ENTITY_ID: AIR_PURIFIER_ENTITY_ID,
                FanServiceArgument.PERCENTAGE: 50,
            },
            blocking=True,
        )

    assert mock_onecta_client.patch_characteristic.await_args_list == [
        (
            (
                device.id,
                replacement_point.embedded_id,
                "fanControl",
                2,
            ),
            {"path": "/airPurificationModes/manualFan/fanSpeed/modes/fixed"},
        )
    ]


async def test_air_purifier_rejects_manual_speed_as_preset(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """The HA preset action must not expose the native manual speed mode."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    command = _execute_typed_command(config_entry, mock_onecta_client)
    config_entry.runtime_data.async_execute_command = command

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {
                ATTR_ENTITY_ID: AIR_PURIFIER_ENTITY_ID,
                FanServiceArgument.PRESET_MODE: "manualFan",
            },
            blocking=True,
        )

    command.assert_not_awaited()


async def test_air_purifier_ignores_missing_mode_value(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Ignore a null current mode when building preset options."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    coordinator = config_entry.runtime_data
    execute = _execute_typed_command(config_entry, mock_onecta_client)
    coordinator.async_execute_command = execute
    purification = _air_purification(config_entry)
    assert purification.mode is not None
    purification.mode.value = None

    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    entity = hass.data[FAN_DOMAIN].get_entity(AIR_PURIFIER_ENTITY_ID)
    assert isinstance(entity, DaikinAirPurifier)
    assert entity.preset_modes == [
        "auto_fan",
        "econo",
        "anti_pollen",
        "circulator",
        "auto",
        "moist",
    ]

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {
            ATTR_ENTITY_ID: AIR_PURIFIER_ENTITY_ID,
            FanServiceArgument.PRESET_MODE: "auto_fan",
        },
        blocking=True,
    )

    execute.assert_awaited_once()


async def test_air_purifier_does_not_expose_read_only_preset_modes(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """A read-only native mode is omitted from the HA fan preset service."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    coordinator = config_entry.runtime_data
    execute = _execute_typed_command(config_entry, mock_onecta_client)
    coordinator.async_execute_command = execute
    purification = _air_purification(config_entry)
    assert purification.mode is not None
    purification.mode.settable = False
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    state = hass.states.get(AIR_PURIFIER_ENTITY_ID)
    assert state is not None
    assert not state.attributes.get(FanEntityCapabilityAttribute.PRESET_MODES)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {
                ATTR_ENTITY_ID: state.entity_id,
                FanServiceArgument.PRESET_MODE: "auto_fan",
            },
            blocking=True,
        )
    execute.assert_not_awaited()


async def test_air_purifier_clears_state_when_purification_disappears(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Clear stale controls when a poll omits air-purification data."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    entity = hass.data[FAN_DOMAIN].get_entity(AIR_PURIFIER_ENTITY_ID)
    assert isinstance(entity, DaikinAirPurifier)
    device = next(iter(config_entry.runtime_data.data.values())).device
    management_point = device.management_points_by_type("climateControl")[0]
    management_point.characteristics.pop("airPurificationMode")

    entity.update_state()

    assert entity.preset_mode is None
    assert entity.preset_modes == []
    assert entity.percentage is None
    assert entity.supported_features == FanEntityFeature(0)


async def test_air_purifier_hides_invalid_fixed_speed_control(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Do not advertise percentage control for malformed native speed data."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    coordinator = config_entry.runtime_data
    execute = _execute_typed_command(config_entry, mock_onecta_client)
    coordinator.async_execute_command = execute
    purification = _air_purification(config_entry)
    operation = purification.fan_operation("manualFan")
    assert operation is not None and operation.fan_speed is not None
    assert operation.fan_speed.modes is not None
    operation.fan_speed.modes[FANMODE_FIXED].step_value = 0
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    state = hass.states.get(AIR_PURIFIER_ENTITY_ID)
    assert state is not None
    assert not state.attributes[ATTR_SUPPORTED_FEATURES] & FanEntityFeature.SET_SPEED
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PERCENTAGE,
            {
                ATTR_ENTITY_ID: state.entity_id,
                FanServiceArgument.PERCENTAGE: 50,
            },
            blocking=True,
        )
    execute.assert_not_awaited()


async def test_air_purifier_turn_on_rejects_preset_and_percentage(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Reject conflicting arguments before any power or mode write."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    execute = _execute_typed_command(config_entry, mock_onecta_client)
    config_entry.runtime_data.async_execute_command = execute
    purification = _air_purification(config_entry)
    assert purification.power is not None
    purification.power.value = "off"
    config_entry.runtime_data.async_update_listeners()
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            FAN_DOMAIN,
            FAN_SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: AIR_PURIFIER_ENTITY_ID,
                FanServiceArgument.PRESET_MODE: "auto_fan",
                FanServiceArgument.PERCENTAGE: 65,
            },
            blocking=True,
        )

    assert err.value.translation_key == "air_purifier_preset_and_percentage"
    execute.assert_not_awaited()
    assert purification.power.value == "off"


@pytest.mark.parametrize(
    ("service_data", "expected_preset", "expected_percentage"),
    [
        pytest.param(
            {FanServiceArgument.PRESET_MODE: "auto_fan"},
            "auto_fan",
            None,
            id="preset-only",
        ),
        pytest.param(
            {FanServiceArgument.PERCENTAGE: 65},
            None,
            75,
            id="percentage-only",
        ),
    ],
)
async def test_air_purifier_turn_on_applies_one_optional_control(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    service_data: dict[str, str | int],
    expected_preset: str | None,
    expected_percentage: int | None,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Apply either a preset or a manual speed through the HA fan service."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    execute = _execute_typed_command(config_entry, mock_onecta_client)
    config_entry.runtime_data.async_execute_command = execute

    await hass.services.async_call(
        FAN_DOMAIN,
        FAN_SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: AIR_PURIFIER_ENTITY_ID, **service_data},
        blocking=True,
    )

    state = hass.states.get(AIR_PURIFIER_ENTITY_ID)
    assert state is not None
    assert state.state == "on"
    assert state.attributes[FanEntityStateAttribute.PRESET_MODE] == expected_preset
    assert state.attributes[FanEntityStateAttribute.PERCENTAGE] == expected_percentage
    execute.assert_awaited()


async def test_air_purifier_turn_off_is_noop_when_already_off(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Avoid a cloud write through HA when the purifier is already off."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    execute = _execute_typed_command(config_entry, mock_onecta_client)
    config_entry.runtime_data.async_execute_command = execute
    await hass.services.async_call(
        FAN_DOMAIN,
        FAN_SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: AIR_PURIFIER_ENTITY_ID},
        blocking=True,
    )
    execute.reset_mock()

    await hass.services.async_call(
        FAN_DOMAIN,
        FAN_SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: AIR_PURIFIER_ENTITY_ID},
        blocking=True,
    )

    execute.assert_not_awaited()


async def test_air_purifier_zero_percentage_turns_off(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Map zero fan percentage to power off through the HA fan service."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    config_entry.runtime_data.async_execute_command = _execute_typed_command(
        config_entry, mock_onecta_client
    )
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {
            ATTR_ENTITY_ID: AIR_PURIFIER_ENTITY_ID,
            FanServiceArgument.PERCENTAGE: 0,
        },
        blocking=True,
    )

    state = hass.states.get(AIR_PURIFIER_ENTITY_ID)
    assert state is not None and state.state == "off"


async def test_air_purifier_percentage_rejects_missing_speed_after_mode_change(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_onecta_client: MockOnectaClient,
) -> None:
    """Reject percentage service if the mode change removes speed data."""
    await _async_setup_fixture(hass, config_entry, "mc80z")
    coordinator = config_entry.runtime_data
    execute = _execute_typed_command(config_entry, mock_onecta_client)
    coordinator.async_execute_command = execute
    gateway = next(iter(coordinator.data.values()))
    point = gateway.device.management_points_by_type("climateControl")[0]

    def remove_air_purification(*_args, **_kwargs) -> None:
        point.characteristics.pop("airPurificationMode")

    mock_onecta_client.patch_characteristic.side_effect = remove_air_purification
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PERCENTAGE,
            {
                ATTR_ENTITY_ID: AIR_PURIFIER_ENTITY_ID,
                FanServiceArgument.PERCENTAGE: 50,
            },
            blocking=True,
        )

    assert err.value.translation_key == "air_purifier_speed_unavailable"
    assert execute.await_count == 1
