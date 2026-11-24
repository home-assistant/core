"""Test IntelliClima Fans."""

from collections.abc import AsyncGenerator
from copy import deepcopy
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyintelliclima.const import FanMode, FanSpeed
from pyintelliclima.intelliclima_types import IntelliClimaDevices
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import async_poll, setup_integration

FAN_ENTITY_ID = "fan.test_vmc"


@pytest.fixture(autouse=True)
async def setup_intelliclima_fan_only(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_interface: AsyncMock,
    mixed_eco_devices: IntelliClimaDevices,
) -> AsyncGenerator[None]:
    """Set up IntelliClima integration with only the fan platform."""
    mock_cloud_interface.get_all_device_status.return_value = mixed_eco_devices
    with patch("homeassistant.components.intelliclima.PLATFORMS", [Platform.FAN]):
        await setup_integration(hass, mock_config_entry)
        # Let tests run against this initialized state
        yield


async def test_all_fan_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_cloud_interface: AsyncMock,
) -> None:
    """Test all entities."""

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_fan_turn_off_service_calls_api(
    hass: HomeAssistant,
    mock_cloud_interface: AsyncMock,
) -> None:
    """fan.turn_off should call ecocomfort.turn_off and refresh."""
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: FAN_ENTITY_ID},
        blocking=True,
    )

    # Device serial from single_eco_device.crono_sn
    mock_cloud_interface.ecocomfort2.turn_off.assert_awaited_once_with("11223344")
    mock_cloud_interface.ecocomfort2.set_mode_speed.assert_not_awaited()


async def test_fan_turn_on_service_calls_api(
    hass: HomeAssistant,
    mock_cloud_interface: AsyncMock,
) -> None:
    """fan.turn_on should call ecocomfort.turn_on and refresh."""
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: FAN_ENTITY_ID,
            ATTR_PERCENTAGE: 30,
        },
        blocking=True,
    )

    # Device serial from single_eco_device.crono_sn
    mock_cloud_interface.ecocomfort2.set_mode_speed.assert_awaited_once_with(
        "11223344", FanMode.inward, FanSpeed.low
    )


async def test_fan_set_percentage_maps_to_speed(
    hass: HomeAssistant,
    mock_cloud_interface: AsyncMock,
) -> None:
    """fan.set_percentage maps to closest IntelliClima speed via set_mode_speed."""
    # 15% is closest to 25% (sleep).
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: FAN_ENTITY_ID, ATTR_PERCENTAGE: 15},
        blocking=True,
    )
    # Initial mode_set=FanMode.inward from single_eco_device.
    # Sleep speed is FanSpeed.sleep (25%).
    mock_cloud_interface.ecocomfort2.set_mode_speed.assert_awaited_once_with(
        "11223344", FanMode.inward, FanSpeed.sleep
    )


async def test_fan_set_preset_mode_service(
    hass: HomeAssistant,
    mock_cloud_interface: AsyncMock,
) -> None:
    """Test set preset mode service triggers correct api call."""

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PRESET_MODE,
        {ATTR_ENTITY_ID: FAN_ENTITY_ID, ATTR_PRESET_MODE: "auto"},
        blocking=True,
    )

    mock_cloud_interface.ecocomfort2.set_mode_speed_auto.assert_awaited_once_with(
        "11223344"
    )
    mock_cloud_interface.ecocomfort2.turn_off.assert_not_awaited()


async def test_fan_set_percentage_zero_turns_off(
    hass: HomeAssistant,
    mock_cloud_interface: AsyncMock,
) -> None:
    """Setting percentage to 0 should call turn_off, not set_mode_speed."""
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: FAN_ENTITY_ID, ATTR_PERCENTAGE: 0},
        blocking=True,
    )

    mock_cloud_interface.ecocomfort2.turn_off.assert_awaited_once_with("11223344")
    mock_cloud_interface.ecocomfort2.set_mode_speed.assert_not_awaited()


@pytest.mark.parametrize(
    ("service_data", "expected_mode", "expected_speed"),
    [
        # percentage=None, preset_mode=None -> defaults to previous
        # speed > 75% (medium), previous mode > FanMode.inward
        ({}, FanMode.inward, FanSpeed.medium),
        # percentage=0, preset_mode=None -> default 25%
        # (FanSpeed.sleep), previous mode (inward)
        ({ATTR_PERCENTAGE: 0}, FanMode.inward, FanSpeed.sleep),
    ],
)
async def test_fan_turn_on_defaulting_behavior(
    hass: HomeAssistant,
    mock_cloud_interface: AsyncMock,
    service_data: dict,
    expected_mode: FanMode,
    expected_speed: FanSpeed,
) -> None:
    """turn_on defaults percentage/preset as expected."""
    data = {ATTR_ENTITY_ID: FAN_ENTITY_ID} | service_data

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        data,
        blocking=True,
    )

    mock_cloud_interface.ecocomfort2.set_mode_speed.assert_awaited_once_with(
        "11223344", expected_mode, expected_speed
    )
    mock_cloud_interface.ecocomfort2.turn_off.assert_not_awaited()


async def test_fan_turn_on_when_off_without_percentage(
    hass: HomeAssistant,
    mock_cloud_interface: AsyncMock,
    single_eco_device: IntelliClimaDevices,
) -> None:
    """turn_on without percentage on an off fan turns it on at sleep speed."""
    eco = single_eco_device.ecocomfort2_devices["56789"]
    eco.mode_set = FanMode.off
    eco.mode_state = "0"
    eco.speed_set = FanSpeed.off
    eco.speed_state = "0"

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: FAN_ENTITY_ID},
        blocking=True,
    )

    mock_cloud_interface.ecocomfort2.set_mode_speed.assert_awaited_once_with(
        "11223344", FanMode.alternate, FanSpeed.sleep
    )
    mock_cloud_interface.ecocomfort2.turn_off.assert_not_awaited()


async def test_fan_turn_on_defaulting_behavior_auto_preset(
    hass: HomeAssistant,
    mock_cloud_interface: AsyncMock,
) -> None:
    """turn_on with auto preset mode calls auto request."""

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: FAN_ENTITY_ID, ATTR_PRESET_MODE: "auto"},
        blocking=True,
    )

    mock_cloud_interface.ecocomfort2.set_mode_speed_auto.assert_awaited_once_with(
        "11223344"
    )
    mock_cloud_interface.ecocomfort2.turn_off.assert_not_awaited()


@pytest.mark.parametrize(
    ("device_family", "device_id", "entity_id"),
    [
        pytest.param("ecocomfort2_devices", "56789", "fan.test_vmc", id="eco2"),
        pytest.param("ecocomfort3_devices", "33333", "fan.test_vmc_3", id="eco3"),
    ],
)
@pytest.mark.parametrize(
    ("mode_state", "speed_state", "state", "percentage", "preset_mode"),
    [
        pytest.param("0", "0", STATE_OFF, 0, None, id="off"),
        pytest.param("3", "2", STATE_ON, 50, None, id="manual_alternate_low"),
        pytest.param("1", "3", STATE_ON, 75, None, id="manual"),
        pytest.param("3", str(0x40 | 3), STATE_ON, 100, None, id="boost"),
        pytest.param("2", str(0x80 | 3), STATE_ON, 25, None, id="night"),
        pytest.param("1", str(0x20 | 2), STATE_ON, 75, None, id="advanced"),
        pytest.param("1", str(0x10 | 3), STATE_ON, 75, None, id="program"),
        pytest.param("4", str(0x10 | 2), STATE_ON, 50, "auto", id="auto"),
        pytest.param("4", str(0x10), STATE_ON, 0, "auto", id="auto_idle"),
        pytest.param("4", "3", STATE_ON, 75, None, id="sensor_manual_speed"),
        pytest.param("7", "3", STATE_UNKNOWN, None, None, id="undefined"),
    ],
)
async def test_fan_running_state(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mixed_eco_devices: IntelliClimaDevices,
    device_family: str,
    device_id: str,
    entity_id: str,
    mode_state: str,
    speed_state: str,
    state: str,
    percentage: int | None,
    preset_mode: str | None,
) -> None:
    """Test the fan reports the running state rather than the commanded one."""
    eco = getattr(mixed_eco_devices, device_family)[device_id]
    eco.mode_state = mode_state
    eco.speed_state = speed_state
    await async_poll(hass, freezer)

    assert (fan_state := hass.states.get(entity_id))
    assert fan_state.state == state
    assert fan_state.attributes.get(ATTR_PERCENTAGE) == percentage
    assert fan_state.attributes.get(ATTR_PRESET_MODE) == preset_mode


async def test_fan_turn_on_during_boost_keeps_commanded_speed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_cloud_interface: AsyncMock,
    single_eco_device: IntelliClimaDevices,
) -> None:
    """turn_on without percentage resends the commanded speed, not a boost override."""
    eco = single_eco_device.ecocomfort2_devices["56789"]
    eco.speed_state = str(0x40 | 3)
    await async_poll(hass, freezer)

    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: FAN_ENTITY_ID},
        blocking=True,
    )

    mock_cloud_interface.ecocomfort2.set_mode_speed.assert_awaited_once_with(
        "11223344", FanMode.inward, FanSpeed.medium
    )


@pytest.mark.parametrize(
    ("service", "data", "method", "args"),
    [
        pytest.param(SERVICE_TURN_OFF, {}, "turn_off", ("AABBCCDD",), id="off"),
        pytest.param(
            SERVICE_SET_PRESET_MODE,
            {ATTR_PRESET_MODE: "auto"},
            "set_mode_speed_auto",
            ("AABBCCDD",),
            id="auto",
        ),
        pytest.param(
            SERVICE_SET_PERCENTAGE,
            {ATTR_PERCENTAGE: 75},
            "set_mode_speed",
            ("AABBCCDD", FanMode.sensor, FanSpeed.medium),
            id="speed",
        ),
    ],
)
async def test_eco3_commands_use_own_api(
    hass: HomeAssistant,
    mock_cloud_interface: AsyncMock,
    service: str,
    data: dict[str, str | int],
    method: str,
    args: tuple[str | FanMode | FanSpeed, ...],
) -> None:
    """Route ECO3 fan commands to its API without commanding the ECO2 unit."""
    await hass.services.async_call(
        FAN_DOMAIN, service, {ATTR_ENTITY_ID: "fan.test_vmc_3"} | data, blocking=True
    )
    getattr(mock_cloud_interface.ecocomfort3, method).assert_awaited_once_with(*args)
    mock_cloud_interface.ecocomfort2.turn_off.assert_not_awaited()
    mock_cloud_interface.ecocomfort2.set_mode_speed_auto.assert_not_awaited()
    mock_cloud_interface.ecocomfort2.set_mode_speed.assert_not_awaited()


async def test_eco3_turn_on_preserves_commanded_speed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_cloud_interface: AsyncMock,
    mixed_eco_devices: IntelliClimaDevices,
) -> None:
    """Turning ECO3 on during boost preserves the commanded speed."""
    device = mixed_eco_devices.ecocomfort3_devices["33333"]
    device.speed_set = FanSpeed.low
    device.speed_state = "67"
    await async_poll(hass, freezer)

    await hass.services.async_call(
        FAN_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: "fan.test_vmc_3"}, blocking=True
    )
    mock_cloud_interface.ecocomfort3.set_mode_speed.assert_awaited_once_with(
        "AABBCCDD", FanMode.sensor, FanSpeed.low
    )


async def test_mixed_account_refresh(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_cloud_interface: AsyncMock,
    mixed_eco_devices: IntelliClimaDevices,
) -> None:
    """Each model reads the replacement device map supplied by the next poll."""
    updated_devices = deepcopy(mixed_eco_devices)
    updated_devices.ecocomfort2_devices["56789"].speed_state = "3"
    updated_devices.ecocomfort3_devices["33333"].speed_state = "4"
    mock_cloud_interface.get_all_device_status.reset_mock()
    mock_cloud_interface.get_all_device_status.return_value = updated_devices
    await async_poll(hass, freezer)

    mock_cloud_interface.get_all_device_status.assert_awaited_once()
    assert hass.states.get(FAN_ENTITY_ID).attributes[ATTR_PERCENTAGE] == 75
    assert hass.states.get("fan.test_vmc_3").attributes[ATTR_PERCENTAGE] == 100


async def test_device_disappears_from_mixed_account(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_cloud_interface: AsyncMock,
    single_eco_device: IntelliClimaDevices,
) -> None:
    """A missing ECO3 becomes unavailable while ECO2 remains available."""
    mock_cloud_interface.get_all_device_status.reset_mock()
    mock_cloud_interface.get_all_device_status.return_value = single_eco_device
    await async_poll(hass, freezer)

    mock_cloud_interface.get_all_device_status.assert_awaited_once()
    assert hass.states.get(FAN_ENTITY_ID).state == STATE_ON
    assert hass.states.get("fan.test_vmc_3").state == STATE_UNAVAILABLE
