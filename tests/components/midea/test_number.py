"""Tests for midea number.py."""

from collections.abc import Callable
from unittest.mock import patch

from midealocal.const import DeviceType
from midealocal.devices.ac import DeviceAttributes as ACAttributes
from midealocal.devices.c2 import DeviceAttributes as C2Attributes
from midealocal.devices.cd import DeviceAttributes as CDAttributes
from midealocal.devices.ed import DeviceAttributes as EDAttributes
from midealocal.devices.fb import DeviceAttributes as FBAttributes
from midealocal.exceptions import SocketException
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_MAX,
    ATTR_MIN,
    ATTR_STEP,
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import DummyDevice, entity_entries
from .const import TEST_DEVICE_ID

from tests.common import MockConfigEntry, snapshot_platform


def _c2_device() -> DummyDevice:
    device = DummyDevice(
        DeviceType.C2,
        attributes={
            C2Attributes.dry_level: 1,
            C2Attributes.water_temp_level: 2,
            C2Attributes.seat_temp_level: 3,
        },
    )
    device.max_dry_level = 3
    device.max_water_temp_level = 5
    device.max_seat_temp_level = 5
    return device


def _cd_device() -> DummyDevice:
    return DummyDevice(
        DeviceType.CD,
        attributes={CDAttributes.vacation_days: 7},
    )


def _ed_device() -> DummyDevice:
    return DummyDevice(
        DeviceType.ED,
        attributes={
            EDAttributes.water_hardness: 120,
            EDAttributes.flushing_days: 14,
            EDAttributes.leak_water_protection_value: 500,
        },
    )


def _fb_device() -> DummyDevice:
    return DummyDevice(
        DeviceType.FB,
        attributes={FBAttributes.heating_level: 5},
    )


async def _assert_service_call(
    hass: HomeAssistant,
    entity_id: str,
    value: float,
    expected_calls: list[tuple],
    device: DummyDevice,
) -> None:
    """Call number.set_value and assert the fake device recorded the right call."""
    device.calls.clear()
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
        blocking=True,
    )
    assert device.calls == expected_calls


@pytest.mark.parametrize(
    "device",
    [
        pytest.param(_c2_device(), id="c2"),
        pytest.param(_cd_device(), id="cd"),
        pytest.param(_ed_device(), id="ed"),
        pytest.param(_fb_device(), id="fb"),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_number_state_snapshot(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device: DummyDevice,
) -> None:
    """Test async_setup_entry creates the right number entities per device type."""
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, config_entry, device)

        await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_c2_number_dynamic_max_and_services(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test C2 number entities read their max from a device property and can be set."""
    device = _c2_device()
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_dry_level"]
    assert (state := hass.states.get(entity_entry.entity_id)) is not None
    assert float(state.state) == 1
    assert state.attributes[ATTR_MIN] == 0
    assert state.attributes[ATTR_MAX] == 3
    assert state.attributes[ATTR_STEP] == 1

    await _assert_service_call(
        hass,
        entity_entry.entity_id,
        2,
        [("set_attribute", "dry_level", 2)],
        device,
    )

    water_entry = entity_entries(hass, config_entry)[
        f"{TEST_DEVICE_ID}_water_temp_level"
    ]
    assert (water_state := hass.states.get(water_entry.entity_id)) is not None
    assert water_state.attributes[ATTR_MAX] == 5

    seat_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_seat_temp_level"]
    assert (seat_state := hass.states.get(seat_entry.entity_id)) is not None
    assert seat_state.attributes[ATTR_MAX] == 5


async def test_cd_number_static_range(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test CD's vacation_days uses a static min/max/step range."""
    device = _cd_device()
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_vacation_days"]
    assert (state := hass.states.get(entity_entry.entity_id)) is not None
    assert float(state.state) == 7
    assert state.attributes[ATTR_MIN] == 1
    assert state.attributes[ATTR_MAX] == 360

    await _assert_service_call(
        hass,
        entity_entry.entity_id,
        30,
        [("set_attribute", "vacation_days", 30)],
        device,
    )


async def test_ed_number_entities(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test ED exposes water_hardness, flushing_days and leak_water_protection_value."""
    device = _ed_device()
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, config_entry, device)

    entities = entity_entries(hass, config_entry)
    assert f"{TEST_DEVICE_ID}_water_hardness" in entities
    assert f"{TEST_DEVICE_ID}_flushing_days" in entities
    assert f"{TEST_DEVICE_ID}_leak_water_protection_value" in entities

    leak_entry = entities[f"{TEST_DEVICE_ID}_leak_water_protection_value"]
    await _assert_service_call(
        hass,
        leak_entry.entity_id,
        550,
        [("set_attribute", "leak_water_protection_value", 550)],
        device,
    )


async def test_fb_heating_level(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test FB's heating_level number entity."""
    device = _fb_device()
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_heating_level"]
    assert (state := hass.states.get(entity_entry.entity_id)) is not None
    assert float(state.state) == 5

    await _assert_service_call(
        hass,
        entity_entry.entity_id,
        8,
        [("set_attribute", "heating_level", 8)],
        device,
    )


async def test_number_unknown_when_attribute_not_numeric(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test native_value gracefully reports unknown if a later update clears it."""
    device = _fb_device()
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_heating_level"]
    assert (state := hass.states.get(entity_entry.entity_id))
    assert float(state.state) == 5

    device.attributes[FBAttributes.heating_level] = None
    device.notify_update({FBAttributes.heating_level: None})
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_entry.entity_id))
    assert state.state == "unknown"


async def test_number_not_created_when_attribute_missing(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test no number entity is created when the device does not report the attribute."""
    device = DummyDevice(DeviceType.FB, attributes={})
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, config_entry, device)

    assert entity_entries(hass, config_entry) == {}


async def test_number_not_created_for_other_device_type(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test no number entity is created for a device type without one (e.g. AC's fan_speed)."""
    device = DummyDevice(
        DeviceType.AC,
        attributes={
            ACAttributes.power: True,
            ACAttributes.mode: 1,
            ACAttributes.target_temperature: 22.0,
            ACAttributes.indoor_temperature: 21.0,
            ACAttributes.fan_speed: 60,
        },
    )
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, config_entry, device)

    assert entity_entries(hass, config_entry) == {}


async def test_number_set_value_raises_on_device_communication_error(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test a device communication failure surfaces as a HomeAssistantError."""
    device = _fb_device()
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.NUMBER]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_heating_level"]

    with (
        patch.object(device, "set_attribute", side_effect=SocketException("offline")),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_entry.entity_id, ATTR_VALUE: 3},
            blocking=True,
        )
