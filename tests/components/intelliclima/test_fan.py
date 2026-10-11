"""Test IntelliClima Fans."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pyintelliclima.const import FanMode, FanSpeed
from pyintelliclima.intelliclima_types import IntelliClimaDevices
import pytest
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
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import async_poll, setup_integration

from tests.common import MockConfigEntry, snapshot_platform

FAN_ENTITY_ID = "fan.test_vmc"


@pytest.fixture(autouse=True)
async def setup_intelliclima_fan_only(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_interface: AsyncMock,
) -> AsyncGenerator[None]:
    """Set up IntelliClima integration with only the fan platform."""
    with patch("homeassistant.components.intelliclima.PLATFORMS", [Platform.FAN]):
        await setup_integration(hass, mock_config_entry)
        # Let tests run against this initialized state
        yield


async def test_all_fan_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_cloud_interface: AsyncMock,
) -> None:
    """Test all entities."""

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    # There should be exactly one fan entity
    fan_entries = [
        entry
        for entry in entity_registry.entities.values()
        if entry.platform == "intelliclima" and entry.domain == FAN_DOMAIN
    ]
    assert len(fan_entries) == 1
    entity_entry = fan_entries[0]

    # Device should exist and match snapshot
    assert entity_entry.device_id
    assert (device_entry := device_registry.async_get(entity_entry.device_id))
    assert device_entry == snapshot


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
    single_eco_device: IntelliClimaDevices,
    mode_state: str,
    speed_state: str,
    state: str,
    percentage: int | None,
    preset_mode: str | None,
) -> None:
    """Test the fan reports the running state rather than the commanded one."""
    eco = single_eco_device.ecocomfort2_devices["56789"]
    eco.mode_state = mode_state
    eco.speed_state = speed_state
    await async_poll(hass, freezer)

    assert (fan_state := hass.states.get(FAN_ENTITY_ID))
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
