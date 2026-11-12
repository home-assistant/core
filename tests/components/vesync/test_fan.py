"""Tests for the fan module."""

from contextlib import nullcontext
from unittest.mock import AsyncMock, _Call, call, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from pyvesync.devices.vesyncfan import VeSyncPedestalFan, VeSyncTowerFan
from pyvesync.devices.vesyncpurifier import VeSyncAirBaseV2
from pyvesync.utils.errors import ResponseInfo
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fan import (
    ATTR_OSCILLATING,
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    DOMAIN as FAN_DOMAIN,
    SERVICE_OSCILLATE,
    SERVICE_SET_PERCENTAGE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import (
    ALL_DEVICE_NAMES,
    ENTITY_FAN,
    ENTITY_PEDESTAL_FAN,
    mock_devices_response,
)

NoException = nullcontext()
DEVICE_ERROR = ResponseInfo(name="error", error_type="error", message="Device error")


async def _fail_without_response(
    device: VeSyncTowerFan | VeSyncPedestalFan, *args: bool
) -> bool:
    """Simulate a device command that failed without an API response."""
    device.last_response = None
    return False


@pytest.mark.parametrize("device_name", ALL_DEVICE_NAMES)
async def test_fan_state(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
    device_name: str,
) -> None:
    """Test the resulting setup state is as expected for the platform."""

    # Configure the API devices call for device_name
    mock_devices_response(aioclient_mock, device_name)

    # setup platform - only including the named device
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check device registry
    devices = dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    assert devices == snapshot(name="devices")

    # Check entity registry
    entities = [
        entity
        for entity in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        if entity.domain == FAN_DOMAIN
    ]
    assert entities == snapshot(name="entities")

    # Check states
    for entity in entities:
        assert hass.states.get(entity.entity_id) == snapshot(name=entity.entity_id)


@pytest.mark.parametrize(
    ("action", "command"),
    [
        (SERVICE_TURN_ON, "pyvesync.devices.vesyncfan.VeSyncTowerFan.turn_on"),
        (SERVICE_TURN_OFF, "pyvesync.devices.vesyncfan.VeSyncTowerFan.turn_off"),
    ],
)
async def test_turn_on_off_success(
    hass: HomeAssistant,
    fan_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    action: str,
    command: str,
) -> None:
    """Test turn_on and turn_off method."""

    mock_devices_response(aioclient_mock, "SmartTowerFan")

    with (
        patch(command, new_callable=AsyncMock, return_value=True) as method_mock,
    ):
        with patch(
            "homeassistant.components.vesync.fan.VeSyncFanHA.async_write_ha_state"
        ) as update_mock:
            await hass.services.async_call(
                FAN_DOMAIN,
                action,
                {ATTR_ENTITY_ID: ENTITY_FAN},
                blocking=True,
            )

        await hass.async_block_till_done()
        method_mock.assert_called_once()
        update_mock.assert_called_once()


@pytest.mark.parametrize(
    ("action", "command"),
    [
        (
            SERVICE_TURN_ON,
            "pyvesync.base_devices.vesyncbasedevice.VeSyncBaseToggleDevice.turn_on",
        ),
        (
            SERVICE_TURN_OFF,
            "pyvesync.base_devices.vesyncbasedevice.VeSyncBaseToggleDevice.turn_off",
        ),
    ],
)
async def test_turn_on_off_raises_error(
    hass: HomeAssistant,
    fan_config_entry: MockConfigEntry,
    action: str,
    command: str,
) -> None:
    """Test turn_on and turn_off raises errors when fails."""

    # returns False indicating failure in which case raises HomeAssistantError.
    with (
        patch(
            command,
            return_value=False,
        ) as method_mock,
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            FAN_DOMAIN,
            action,
            {ATTR_ENTITY_ID: ENTITY_FAN},
            blocking=True,
        )

    await hass.async_block_till_done()
    method_mock.assert_called_once()


@pytest.mark.parametrize(
    ("api_response", "expectation"),
    [(True, NoException), (False, pytest.raises(HomeAssistantError))],
)
@pytest.mark.parametrize(
    ("preset_mode", "patch_target"),
    [
        ("normal", "pyvesync.devices.vesyncfan.VeSyncTowerFan.set_normal_mode"),
        (
            "sleep",
            "pyvesync.devices.vesyncfan.VeSyncTowerFan.set_sleep_mode",
        ),
        ("turbo", "pyvesync.devices.vesyncfan.VeSyncTowerFan.set_turbo_mode"),
        ("auto", "pyvesync.devices.vesyncfan.VeSyncTowerFan.set_auto_mode"),
    ],
)
async def test_set_preset_mode(
    hass: HomeAssistant,
    fan_config_entry: MockConfigEntry,
    api_response: bool,
    expectation,
    preset_mode: str,
    patch_target: str,
) -> None:
    """Test set_preset_mode method via turn on for test coverage."""

    # If VeSyncTowerFan.mode fails (returns False), then HomeAssistantError is raised
    with (
        expectation,
        patch(
            patch_target,
            return_value=api_response,
        ) as method_mock,
    ):
        with patch(
            "homeassistant.components.vesync.fan.VeSyncFanHA.async_write_ha_state"
        ) as update_mock:
            await hass.services.async_call(
                FAN_DOMAIN,
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: ENTITY_FAN, ATTR_PRESET_MODE: preset_mode},
                blocking=True,
            )

        await hass.async_block_till_done()
        method_mock.assert_called_once()
        update_mock.assert_called_once()


async def test_out_of_range_fan_level(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that an out-of-range fan level produces an unknown percentage."""

    mock_devices_response(
        aioclient_mock, "CoreBreeze 432S", details_override={"fanSpeedLevel": -1}
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_PEDESTAL_FAN)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
    assert state.attributes[ATTR_PERCENTAGE] is None


async def test_set_preset_mode_eco(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the eco preset is exposed, reflected, and sets the mode via set_mode."""
    mock_devices_response(
        aioclient_mock, "CoreBreeze 432S", details_override={"workMode": "eco"}
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_PEDESTAL_FAN)
    assert state is not None
    assert "eco" in state.attributes[ATTR_PRESET_MODES]
    assert state.attributes[ATTR_PRESET_MODE] == "eco"

    with (
        patch(
            "pyvesync.devices.vesyncfan.VeSyncPedestalFan.set_mode",
            new_callable=AsyncMock,
            return_value=True,
        ) as method_mock,
        patch(
            "homeassistant.components.vesync.fan.VeSyncFanHA.async_write_ha_state"
        ) as update_mock,
    ):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_PEDESTAL_FAN, ATTR_PRESET_MODE: "eco"},
            blocking=True,
        )
        await hass.async_block_till_done()

    method_mock.assert_awaited_once_with("eco")
    update_mock.assert_called_once()


@pytest.mark.parametrize(
    ("action", "api_response", "expectation"),
    [
        ("true", True, NoException),
        ("false", True, NoException),
        ("true", False, pytest.raises(HomeAssistantError)),
    ],
)
async def test_pedestal_fan_oscillation(
    hass: HomeAssistant,
    pedestal_fan_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    action: str,
    api_response: bool,
    expectation,
) -> None:
    """Test oscillation on and off for pedestal fans.

    Pedestal fans (e.g. CoreBreeze 432S / LPF-R432S) expose vertical and
    horizontal oscillation as separate toggles. The HA oscillate switch
    should control both axes together.
    """

    with (
        expectation,
        patch(
            "pyvesync.devices.vesyncfan.VeSyncPedestalFan.toggle_vertical_oscillation",
            new_callable=AsyncMock,
            return_value=api_response,
        ) as vertical_mock,
        patch(
            "pyvesync.devices.vesyncfan.VeSyncPedestalFan."
            "toggle_horizontal_oscillation",
            new_callable=AsyncMock,
            return_value=api_response,
        ) as horizontal_mock,
    ):
        with patch(
            "homeassistant.components.vesync.fan.VeSyncFanHA.async_write_ha_state"
        ) as update_mock:
            await hass.services.async_call(
                FAN_DOMAIN,
                "oscillate",
                {ATTR_ENTITY_ID: ENTITY_PEDESTAL_FAN, "oscillating": action},
                blocking=True,
            )

        await hass.async_block_till_done()
        vertical_mock.assert_called_once()
        horizontal_mock.assert_called_once()
        update_mock.assert_called_once()


@pytest.mark.parametrize(
    ("action", "command"),
    [
        ("true", "pyvesync.devices.vesyncfan.VeSyncTowerFan.toggle_oscillation"),
        ("false", "pyvesync.devices.vesyncfan.VeSyncTowerFan.toggle_oscillation"),
    ],
)
@pytest.mark.parametrize(
    ("api_response", "expectation"),
    [(True, NoException), (False, pytest.raises(HomeAssistantError))],
)
async def test_oscillation_success(
    hass: HomeAssistant,
    fan_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    action: str,
    command: str,
    api_response: bool,
    expectation,
) -> None:
    """Test oscillation on and off."""

    mock_devices_response(aioclient_mock, "SmartTowerFan")

    with (
        expectation,
        patch(
            command, new_callable=AsyncMock, return_value=api_response
        ) as method_mock,
    ):
        with patch(
            "homeassistant.components.vesync.fan.VeSyncFanHA.async_write_ha_state"
        ) as update_mock:
            await hass.services.async_call(
                FAN_DOMAIN,
                "oscillate",
                {ATTR_ENTITY_ID: ENTITY_FAN, "oscillating": action},
                blocking=True,
            )

        await hass.async_block_till_done()
        method_mock.assert_called_once()
        update_mock.assert_called_once()


@pytest.mark.parametrize("service", [SERVICE_SET_PERCENTAGE, SERVICE_TURN_ON])
@pytest.mark.parametrize(
    ("details", "percentage", "expected_calls"),
    [
        pytest.param(
            {"powerSwitch": 1, "workMode": "normal"},
            0,
            [call.turn_off()],
            id="zero_turns_off",
        ),
        pytest.param(
            {"powerSwitch": 1, "workMode": "normal"},
            50,
            [call.set_fan_speed(6)],
            id="on_in_normal_mode",
        ),
        pytest.param(
            {"powerSwitch": 0, "workMode": "normal"},
            50,
            [call.turn_on(), call.set_fan_speed(6)],
            id="off_turns_on_first",
        ),
        pytest.param(
            {"powerSwitch": 1, "workMode": "auto"},
            50,
            [call.set_manual_mode(), call.set_fan_speed(6)],
            id="preset_switches_to_manual_first",
        ),
    ],
)
async def test_set_percentage(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    service: str,
    details: dict[str, int | str],
    percentage: int,
    expected_calls: list[_Call],
) -> None:
    """Test setting the speed sends the required device commands in order."""
    mock_devices_response(aioclient_mock, "SmartTowerFan", details_override=details)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    device = AsyncMock(
        **{
            f"{command}.return_value": True
            for command in (
                "turn_on",
                "turn_off",
                "set_manual_mode",
                "set_fan_speed",
            )
        }
    )
    with patch.multiple(
        "pyvesync.devices.vesyncfan.VeSyncTowerFan",
        turn_on=device.turn_on,
        turn_off=device.turn_off,
        set_manual_mode=device.set_manual_mode,
        set_fan_speed=device.set_fan_speed,
    ):
        await hass.services.async_call(
            FAN_DOMAIN,
            service,
            {ATTR_ENTITY_ID: ENTITY_FAN, ATTR_PERCENTAGE: percentage},
            blocking=True,
        )

    assert device.mock_calls == expected_calls


@pytest.mark.parametrize(
    ("details", "percentage", "command", "last_response", "message"),
    [
        pytest.param(
            {"powerSwitch": 1, "workMode": "normal"},
            0,
            "turn_off",
            DEVICE_ERROR,
            "An error occurred while turning off: Device error",
            id="turn_off_last_response",
        ),
        pytest.param(
            {"powerSwitch": 1, "workMode": "normal"},
            0,
            "turn_off",
            None,
            "Failed to turn off fan, no response found.",
            id="turn_off_no_last_response",
        ),
        pytest.param(
            {"powerSwitch": 0, "workMode": "normal"},
            50,
            "turn_on",
            DEVICE_ERROR,
            "An error occurred while turning on: Device error",
            id="turn_on_last_response",
        ),
        pytest.param(
            {"powerSwitch": 0, "workMode": "normal"},
            50,
            "turn_on",
            None,
            "Failed to turn on fan, no response found.",
            id="turn_on_no_last_response",
        ),
        pytest.param(
            {"powerSwitch": 1, "workMode": "auto"},
            50,
            "set_manual_mode",
            DEVICE_ERROR,
            "An error occurred while setting manual mode.Device error",
            id="set_manual_mode_last_response",
        ),
        pytest.param(
            {"powerSwitch": 1, "workMode": "auto"},
            50,
            "set_manual_mode",
            None,
            "Failed to set manual mode, no response found.",
            id="set_manual_mode_no_last_response",
        ),
        pytest.param(
            {"powerSwitch": 1, "workMode": "normal"},
            50,
            "set_fan_speed",
            DEVICE_ERROR,
            "An error occurred while changing fan speed: Device error",
            id="set_fan_speed_last_response",
        ),
        pytest.param(
            {"powerSwitch": 1, "workMode": "normal"},
            50,
            "set_fan_speed",
            None,
            "Failed to set fan speed, no response found.",
            id="set_fan_speed_no_last_response",
        ),
    ],
)
async def test_set_percentage_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    details: dict[str, int | str],
    percentage: int,
    command: str,
    last_response: ResponseInfo | None,
    message: str,
) -> None:
    """Test a failed device command while setting the speed raises an error."""
    mock_devices_response(aioclient_mock, "SmartTowerFan", details_override=details)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    async def _fail_command(device: VeSyncTowerFan, *args: int) -> bool:
        device.last_response = last_response
        return False

    with (
        patch.object(
            VeSyncTowerFan, command, autospec=True, side_effect=_fail_command
        ) as command_mock,
        pytest.raises(HomeAssistantError, match=message),
    ):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PERCENTAGE,
            {ATTR_ENTITY_ID: ENTITY_FAN, ATTR_PERCENTAGE: percentage},
            blocking=True,
        )

    command_mock.assert_awaited_once()


@pytest.mark.parametrize(
    ("device_name", "entity_id", "details", "expected_percentage"),
    [
        (
            "Air Purifier Vital 200S",
            "fan.air_purifier_vital_200s",
            {"workMode": "pet", "fanSpeedLevel": 3},
            75,
        ),
        (
            "Air Purifier Vital 200S",
            "fan.air_purifier_vital_200s",
            {"workMode": "auto", "fanSpeedLevel": 2},
            50,
        ),
        (
            "Air Purifier Vital 200S",
            "fan.air_purifier_vital_200s",
            {"workMode": "sleep", "fanSpeedLevel": 255},
            None,
        ),
        (
            "Air Purifier 200s",
            "fan.air_purifier_200s",
            {"mode": "sleep", "level": 3},
            None,
        ),
    ],
)
async def test_percentage_in_preset_mode(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    device_name: str,
    entity_id: str,
    details: dict[str, int | str],
    expected_percentage: int | None,
) -> None:
    """Test the running level is reported in presets only where the API has it."""
    mock_devices_response(aioclient_mock, device_name, details_override=details)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[ATTR_PERCENTAGE] == expected_percentage


@pytest.mark.parametrize(
    ("service", "service_data", "command", "message"),
    [
        pytest.param(
            SERVICE_TURN_ON,
            {},
            "turn_on",
            "Failed to turn on fan, no response found.",
            id="turn_on",
        ),
        pytest.param(
            SERVICE_TURN_OFF,
            {},
            "turn_off",
            "Failed to turn off fan, no response found.",
            id="turn_off",
        ),
        pytest.param(
            SERVICE_TURN_ON,
            {ATTR_PRESET_MODE: "auto"},
            "set_auto_mode",
            "Failed to set preset mode, no response found.",
            id="preset_mode",
        ),
        pytest.param(
            SERVICE_OSCILLATE,
            {ATTR_OSCILLATING: True},
            "toggle_oscillation",
            "Failed to set oscillation, no response found.",
            id="oscillate",
        ),
    ],
)
async def test_command_failure_without_response(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    service: str,
    service_data: dict[str, str | bool],
    command: str,
    message: str,
) -> None:
    """Test a failed command with no API response raises a fallback error."""
    mock_devices_response(
        aioclient_mock, "SmartTowerFan", details_override={"powerSwitch": 1}
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    with (
        patch.object(
            VeSyncTowerFan, command, autospec=True, side_effect=_fail_without_response
        ) as command_mock,
        pytest.raises(HomeAssistantError, match=message),
    ):
        await hass.services.async_call(
            FAN_DOMAIN,
            service,
            {ATTR_ENTITY_ID: ENTITY_FAN, **service_data},
            blocking=True,
        )

    command_mock.assert_awaited_once()


async def test_pedestal_fan_oscillation_failure_without_response(
    hass: HomeAssistant,
    pedestal_fan_config_entry: MockConfigEntry,
) -> None:
    """Test a failed pedestal oscillation with no API response raises an error."""
    with (
        patch.object(
            VeSyncPedestalFan,
            "toggle_vertical_oscillation",
            autospec=True,
            side_effect=_fail_without_response,
        ),
        patch.object(
            VeSyncPedestalFan,
            "toggle_horizontal_oscillation",
            autospec=True,
            side_effect=_fail_without_response,
        ),
        pytest.raises(
            HomeAssistantError, match="Failed to set oscillation, no response found."
        ),
    ):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_OSCILLATE,
            {ATTR_ENTITY_ID: ENTITY_PEDESTAL_FAN, ATTR_OSCILLATING: True},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("vertical", "horizontal", "expected"),
    [
        pytest.param(1, 1, True, id="both_axes"),
        pytest.param(1, 0, True, id="vertical_only"),
        pytest.param(0, 1, True, id="horizontal_only"),
        pytest.param(0, 0, False, id="neither_axis"),
    ],
)
async def test_pedestal_fan_oscillating_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    vertical: int,
    horizontal: int,
    expected: bool,
) -> None:
    """Test a pedestal fan is oscillating when either axis is active."""
    mock_devices_response(
        aioclient_mock,
        "CoreBreeze 432S",
        details_override={
            "verticalOscillationState": vertical,
            "horizontalOscillationState": horizontal,
        },
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_PEDESTAL_FAN)
    assert state is not None
    assert state.attributes[ATTR_OSCILLATING] is expected


async def test_preset_mode_not_reported(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test no preset is reported when the library cannot map the work mode."""
    mock_devices_response(
        aioclient_mock, "SmartTowerFan", details_override={"workMode": "unmapped"}
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_FAN)
    assert state is not None
    assert state.attributes[ATTR_PRESET_MODE] is None


async def test_unknown_preset_mode_logs_warning(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test an unknown device mode is reported as no preset and logged."""
    mock_devices_response(
        aioclient_mock, "Air Purifier 200s", details_override={"mode": "unmapped"}
    )

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("fan.air_purifier_200s")
    assert state is not None
    assert state.attributes[ATTR_PRESET_MODE] is None
    assert "Unknown mode 'unmapped'" in caplog.text


async def test_set_preset_mode_pet(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the pet preset is sent to purifiers that support it."""
    mock_devices_response(aioclient_mock, "Air Purifier Vital 200S")

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    with patch.object(
        VeSyncAirBaseV2, "set_pet_mode", new_callable=AsyncMock, return_value=True
    ) as method_mock:
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "fan.air_purifier_vital_200s", ATTR_PRESET_MODE: "pet"},
            blocking=True,
        )

    method_mock.assert_awaited_once_with()
