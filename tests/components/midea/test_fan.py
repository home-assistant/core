"""Tests for midea fan.py."""

from collections.abc import Callable
from unittest.mock import patch

from midealocal.const import DeviceType
from midealocal.devices.ac import DeviceAttributes as ACAttributes
from midealocal.devices.b6 import DeviceAttributes as B6Attributes
from midealocal.devices.ce import DeviceAttributes as CEAttributes, MideaCEDevice
from midealocal.devices.fa import DeviceAttributes as FAAttributes, MideaFADevice
from midealocal.devices.x40 import DeviceAttributes as X40Attributes
from midealocal.exceptions import SocketException
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fan import (
    ATTR_OSCILLATING,
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    DOMAIN as FAN_DOMAIN,
    SERVICE_OSCILLATE,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import DummyDevice, entity_entries
from .const import TEST_DEVICE_ID

from tests.common import MockConfigEntry, snapshot_platform


async def _assert_service_call(
    hass: HomeAssistant,
    entity_id: str,
    service: str,
    service_data: dict,
    expected_calls: list[tuple],
    device: DummyDevice,
) -> None:
    """Call a fan service and assert the fake device recorded the right call."""
    device.calls.clear()
    await hass.services.async_call(
        FAN_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id, **service_data},
        blocking=True,
    )
    assert device.calls == expected_calls


def _fa_device() -> DummyDevice:
    device = DummyDevice(
        DeviceType.FA,
        attributes={
            FAAttributes.power: True,
            FAAttributes.mode: "none",
            FAAttributes.fan_speed: 2,
            FAAttributes.oscillate: True,
        },
    )
    device.speed_count = 3
    device.preset_modes = list(MideaFADevice._modes)
    return device


def _b6_device() -> DummyDevice:
    device = DummyDevice(
        DeviceType.B6,
        attributes={
            B6Attributes.power: True,
            B6Attributes.mode: "Level 1",
            B6Attributes.fan_speed: 1,
        },
    )
    device.speed_count = 2
    return device


def _ce_device() -> DummyDevice:
    device = DummyDevice(
        DeviceType.CE,
        attributes={
            CEAttributes.power: True,
            CEAttributes.mode: "none",
            CEAttributes.fan_speed: 3,
        },
    )
    device.speed_count = 7
    device.preset_modes = list(MideaCEDevice._modes)
    return device


def _x40_device() -> DummyDevice:
    device = DummyDevice(
        DeviceType.X40,
        attributes={X40Attributes.fan_speed: 1},
    )
    device.speed_count = 2
    device.preset_modes = []
    return device


@pytest.mark.parametrize(
    "device",
    [
        pytest.param(_fa_device(), id="fa"),
        pytest.param(_b6_device(), id="b6"),
        pytest.param(_ce_device(), id="ce"),
        pytest.param(_x40_device(), id="x40"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_fan_state_snapshot(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device: DummyDevice,
) -> None:
    """Test async_setup_entry creates the right fan entity per device type."""
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.FAN]):
        await setup_integration(hass, config_entry, device)

        await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("mode", "expected_preset_mode"),
    [
        pytest.param("none", None, id="none_mode"),
        pytest.param("sleep", "sleep", id="preset_mode"),
    ],
)
async def test_fa_fan_services(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
    mode: str,
    expected_preset_mode: str | None,
) -> None:
    """Test FA fan service calls reach the device."""
    device = _fa_device()
    device.attributes[FAAttributes.mode] = mode
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.FAN]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_fan"]

    assert (state := hass.states.get(entity_entry.entity_id)) is not None
    assert state.state == "on"
    assert state.attributes[ATTR_PERCENTAGE] == 66
    assert state.attributes[ATTR_PRESET_MODE] == expected_preset_mode
    assert state.attributes[ATTR_PRESET_MODES] == [
        preset for preset in device.preset_modes if preset != "none"
    ]
    assert state.attributes[ATTR_OSCILLATING] is True

    await _assert_service_call(
        hass,
        entity_entry.entity_id,
        SERVICE_TURN_ON,
        {ATTR_PERCENTAGE: 100},
        [("turn_on", 3, None)],
        device,
    )
    await _assert_service_call(
        hass,
        entity_entry.entity_id,
        SERVICE_TURN_ON,
        {},
        [("turn_on", None, None)],
        device,
    )
    await _assert_service_call(
        hass,
        entity_entry.entity_id,
        SERVICE_SET_PRESET_MODE,
        {ATTR_PRESET_MODE: "sleep"},
        [("set_attribute", "mode", "sleep")],
        device,
    )
    await _assert_service_call(
        hass,
        entity_entry.entity_id,
        SERVICE_OSCILLATE,
        {"oscillating": False},
        [("set_attribute", "oscillate", False)],
        device,
    )
    await _assert_service_call(
        hass,
        entity_entry.entity_id,
        SERVICE_SET_PERCENTAGE,
        {ATTR_PERCENTAGE: 33},
        [("set_attribute", "fan_speed", 1)],
        device,
    )
    await _assert_service_call(
        hass,
        entity_entry.entity_id,
        SERVICE_SET_PERCENTAGE,
        {ATTR_PERCENTAGE: 10},
        [("set_attribute", "fan_speed", 1)],
        device,
    )
    await _assert_service_call(
        hass,
        entity_entry.entity_id,
        SERVICE_SET_PERCENTAGE,
        {ATTR_PERCENTAGE: 0},
        [("set_attribute", "power", False)],
        device,
    )
    await _assert_service_call(
        hass,
        entity_entry.entity_id,
        SERVICE_TURN_OFF,
        {},
        [("set_attribute", "power", False)],
        device,
    )


async def test_ce_fan_turn_on_applies_percentage_and_preset(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test CE turn_on powers on and also applies percentage and preset_mode."""
    device = _ce_device()
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.FAN]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_fan"]

    await _assert_service_call(
        hass,
        entity_entry.entity_id,
        SERVICE_TURN_ON,
        {ATTR_PERCENTAGE: 100, "preset_mode": "eco"},
        [
            ("set_attribute", "power", True),
            ("set_attribute", "fan_speed", 7),
            ("set_attribute", "mode", "eco"),
        ],
        device,
    )
    await _assert_service_call(
        hass,
        entity_entry.entity_id,
        SERVICE_TURN_ON,
        {ATTR_PERCENTAGE: 0},
        [("set_attribute", "power", False)],
        device,
    )


async def test_x40_fan_on_off_and_speed(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test X40 derives is_on from fan_speed and has no power/mode attribute."""
    device = _x40_device()
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.FAN]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_fan"]

    assert (state := hass.states.get(entity_entry.entity_id)) is not None
    assert state.state == "on"
    assert state.attributes[ATTR_PERCENTAGE] == 50
    assert state.attributes[ATTR_PRESET_MODE] is None
    assert ATTR_OSCILLATING not in state.attributes

    await _assert_service_call(
        hass,
        entity_entry.entity_id,
        SERVICE_TURN_ON,
        {ATTR_PERCENTAGE: 100},
        [("set_attribute", "fan_speed", 2)],
        device,
    )
    await _assert_service_call(
        hass,
        entity_entry.entity_id,
        SERVICE_TURN_ON,
        {ATTR_PERCENTAGE: 10},
        [("set_attribute", "fan_speed", 1)],
        device,
    )
    await _assert_service_call(
        hass,
        entity_entry.entity_id,
        SERVICE_TURN_ON,
        {},
        [("set_attribute", "fan_speed", 1)],
        device,
    )
    await _assert_service_call(
        hass,
        entity_entry.entity_id,
        SERVICE_TURN_OFF,
        {},
        [("set_attribute", "fan_speed", 0)],
        device,
    )
    await _assert_service_call(
        hass,
        entity_entry.entity_id,
        SERVICE_TURN_ON,
        {ATTR_PERCENTAGE: 0},
        [("set_attribute", "fan_speed", 0)],
        device,
    )

    device.attributes[X40Attributes.fan_speed] = 0
    device.notify_update({X40Attributes.fan_speed: 0})
    await hass.async_block_till_done()
    assert (state := hass.states.get(entity_entry.entity_id))
    assert state.state == "off"
    assert state.attributes[ATTR_PERCENTAGE] == 0


async def test_fa_fan_unknown_when_attributes_missing(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test power/oscillate gracefully report unknown before the device reports them."""
    device = DummyDevice(DeviceType.FA, attributes={})
    device.speed_count = 3
    device.preset_modes = ["none"]
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.FAN]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_fan"]
    assert (state := hass.states.get(entity_entry.entity_id)) is not None
    assert state.state == "unknown"
    assert state.attributes[ATTR_OSCILLATING] is None


async def test_x40_fan_unknown_when_fan_speed_missing(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test is_on gracefully reports unknown before the device reports fan_speed."""
    device = DummyDevice(DeviceType.X40, attributes={})
    device.speed_count = 2
    device.preset_modes = []
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.FAN]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_fan"]
    assert (state := hass.states.get(entity_entry.entity_id)) is not None
    assert state.state == "unknown"


async def test_fan_not_created_for_other_device_type(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test no fan entity is created for a device type without one."""
    device = DummyDevice(
        DeviceType.AC,
        attributes={
            ACAttributes.power: True,
            ACAttributes.mode: 1,
            ACAttributes.target_temperature: 22.0,
            ACAttributes.indoor_temperature: 21.0,
        },
    )
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.FAN]):
        await setup_integration(hass, config_entry, device)

    assert entity_entries(hass, config_entry) == {}


async def test_fan_turn_on_raises_on_device_communication_error(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test a device communication failure surfaces as a HomeAssistantError."""
    device = _fa_device()
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.FAN]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_fan"]

    with (
        patch.object(device, "turn_on", side_effect=SocketException("offline")),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_entry.entity_id},
            blocking=True,
        )
