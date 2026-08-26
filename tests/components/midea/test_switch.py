"""Tests for midea switch.py."""

from collections.abc import Callable
from unittest.mock import patch

from midealocal.const import DeviceType
from midealocal.devices.ac import DeviceAttributes as ACAttributes
from midealocal.devices.c3 import DeviceAttributes as C3Attributes
from midealocal.devices.cc import DeviceAttributes as CCAttributes
from midealocal.devices.cf import DeviceAttributes as CFAttributes
from midealocal.exceptions import SocketException
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
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
    expected_calls: list[tuple],
    device: DummyDevice,
) -> None:
    """Call a switch service and assert the fake device recorded the right call."""
    device.calls.clear()
    await hass.services.async_call(
        SWITCH_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert device.calls == expected_calls


@pytest.mark.parametrize(
    "device",
    [
        pytest.param(
            DummyDevice(
                DeviceType.AC,
                attributes={
                    ACAttributes.power: True,
                    ACAttributes.mode: 1,
                    ACAttributes.target_temperature: 22.0,
                    ACAttributes.indoor_temperature: 21.0,
                    ACAttributes.aux_heating: True,
                    ACAttributes.breezeless: False,
                    ACAttributes.dry: False,
                    ACAttributes.indirect_wind: False,
                    ACAttributes.natural_wind: False,
                    ACAttributes.prompt_tone: True,
                    ACAttributes.screen_display: True,
                    ACAttributes.screen_display_alternate: False,
                    ACAttributes.out_silent: False,
                    ACAttributes.smart_eye: False,
                    ACAttributes.anion: False,
                    ACAttributes.sound: True,
                    ACAttributes.self_clean: False,
                    ACAttributes.comfort_mode: False,
                    ACAttributes.eco_mode: False,
                    ACAttributes.boost_mode: False,
                    ACAttributes.sleep_mode: False,
                    ACAttributes.frost_protect: False,
                    ACAttributes.swing_vertical: True,
                    ACAttributes.swing_horizontal: True,
                },
            ),
            id="ac",
        ),
        pytest.param(
            DummyDevice(
                DeviceType.C3,
                attributes={
                    C3Attributes.zone1_power: True,
                    C3Attributes.zone2_power: False,
                    C3Attributes.mode: 1,
                    C3Attributes.target_temperature: [22, 23],
                    C3Attributes.disinfect: False,
                    C3Attributes.dhw_power: True,
                    C3Attributes.eco_mode: False,
                    C3Attributes.fast_dhw: False,
                    C3Attributes.silent_mode: True,
                    C3Attributes.tbh: False,
                    C3Attributes.zone1_curve: False,
                    C3Attributes.zone2_curve: True,
                },
            ),
            id="c3",
        ),
        pytest.param(
            DummyDevice(
                DeviceType.CC,
                attributes={
                    CCAttributes.power: True,
                    CCAttributes.mode: 1,
                    CCAttributes.eco_mode: False,
                    CCAttributes.sleep_mode: False,
                    CCAttributes.swing: False,
                    CCAttributes.aux_heating: True,
                    CCAttributes.night_light: False,
                },
            ),
            id="cc",
        ),
        pytest.param(
            DummyDevice(DeviceType.CF, attributes={CFAttributes.aux_heating: True}),
            id="cf",
        ),
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_switch_state_snapshot(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device: DummyDevice,
) -> None:
    """Test async_setup_entry creates the right switch entities per device type."""
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, config_entry, device)

        await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_ac_switch_services(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test AC switch service calls reach the device."""
    device = DummyDevice(
        DeviceType.AC,
        attributes={
            ACAttributes.power: True,
            ACAttributes.mode: 1,
            ACAttributes.target_temperature: 22.0,
            ACAttributes.indoor_temperature: 21.0,
            ACAttributes.aux_heating: False,
        },
    )
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_aux_heating"]

    assert (state := hass.states.get(entity_entry.entity_id)) is not None
    assert state.state == "off"

    await _assert_service_call(
        hass,
        entity_entry.entity_id,
        SERVICE_TURN_ON,
        [("set_attribute", ACAttributes.aux_heating, True)],
        device,
    )
    await _assert_service_call(
        hass,
        entity_entry.entity_id,
        SERVICE_TURN_OFF,
        [("set_attribute", ACAttributes.aux_heating, False)],
        device,
    )


async def test_switch_unknown_when_attribute_becomes_non_bool(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test is_on gracefully reports unknown if a later update clears it."""
    device = DummyDevice(
        DeviceType.AC,
        attributes={
            ACAttributes.power: True,
            ACAttributes.mode: 1,
            ACAttributes.target_temperature: 22.0,
            ACAttributes.indoor_temperature: 21.0,
            ACAttributes.aux_heating: False,
        },
    )
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_aux_heating"]
    assert (state := hass.states.get(entity_entry.entity_id))
    assert state.state == "off"

    device.attributes[ACAttributes.aux_heating] = True
    device.notify_update({ACAttributes.aux_heating: True})
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_entry.entity_id))
    assert state.state == "on"

    device.attributes[ACAttributes.aux_heating] = None
    device.notify_update({ACAttributes.aux_heating: None})
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_entry.entity_id))
    assert state.state == "unknown"


async def test_switch_turn_on_raises_on_device_communication_error(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test a device communication failure surfaces as a HomeAssistantError."""
    device = DummyDevice(
        DeviceType.AC,
        attributes={
            ACAttributes.power: True,
            ACAttributes.mode: 1,
            ACAttributes.target_temperature: 22.0,
            ACAttributes.indoor_temperature: 21.0,
            ACAttributes.aux_heating: False,
        },
    )
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, config_entry, device)

    entity_entry = entity_entries(hass, config_entry)[f"{TEST_DEVICE_ID}_aux_heating"]

    with (
        patch.object(device, "set_attribute", side_effect=SocketException("offline")),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_entry.entity_id},
            blocking=True,
        )


async def test_fb_has_no_switch_entities(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test FB devices, which only expose the climate-owned power attribute, get no switches."""
    device = DummyDevice(DeviceType.FB, attributes={"power": True})
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, config_entry, device)

    assert entity_entries(hass, config_entry) == {}


async def test_switch_not_created_when_attribute_missing(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test a switch is not created when the device does not report the attribute."""
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
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, config_entry, device)

    assert f"{TEST_DEVICE_ID}_aux_heating" not in entity_entries(hass, config_entry)


async def test_switch_not_created_for_climate_owned_attribute(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test no switch is created for attributes already controlled by climate."""
    device = DummyDevice(
        DeviceType.AC,
        attributes={
            ACAttributes.power: True,
            ACAttributes.mode: 1,
            ACAttributes.target_temperature: 22.0,
            ACAttributes.indoor_temperature: 21.0,
            ACAttributes.comfort_mode: False,
            ACAttributes.eco_mode: False,
            ACAttributes.boost_mode: False,
            ACAttributes.sleep_mode: False,
            ACAttributes.frost_protect: False,
            ACAttributes.swing_vertical: True,
            ACAttributes.swing_horizontal: True,
        },
    )
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, config_entry, device)

    created = entity_entries(hass, config_entry)
    for key in (
        "power",
        "comfort_mode",
        "eco_mode",
        "boost_mode",
        "sleep_mode",
        "frost_protect",
        "swing_vertical",
        "swing_horizontal",
    ):
        assert f"{TEST_DEVICE_ID}_{key}" not in created


async def test_switch_not_created_for_other_device_type(
    hass: HomeAssistant,
    mock_config_entry: Callable[[DummyDevice], MockConfigEntry],
) -> None:
    """Test a switch scoped to one device type is not created for another."""
    device = DummyDevice(
        DeviceType.CC,
        attributes={
            CCAttributes.power: True,
            CCAttributes.mode: 1,
            # C3-only attribute name reused here to prove the CC device type
            # is excluded from the description's `models` even when the
            # attribute happens to be present.
            "disinfect": True,
        },
    )
    config_entry = mock_config_entry(device)
    with patch("homeassistant.components.midea._PLATFORMS", [Platform.SWITCH]):
        await setup_integration(hass, config_entry, device)

    assert f"{TEST_DEVICE_ID}_disinfect" not in entity_entries(hass, config_entry)
