"""Modern Ceiling Fan integration tests."""

from collections.abc import AsyncGenerator, Callable
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.bluetooth import (
    generate_advertisement_data,
    generate_ble_device,
    inject_bluetooth_service_info,
)
import switchbot

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.switchbot.const import CONF_ENCRYPTION_KEY, CONF_KEY_ID
from homeassistant.config_entries import SOURCE_BLUETOOTH
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import DOMAIN, patch_async_setup_entry


def service_info(pairing: int = 0) -> BluetoothServiceInfoBleak:
    """Build the device broadcast."""
    return BluetoothServiceInfoBleak.from_device_and_advertisement_data(
        generate_ble_device("AA:BB:CC:DD:EE:FF", "Modern Ceiling Fan"),
        generate_advertisement_data(
            manufacturer_data={
                2409: bytes.fromhex("aabbccddeeff01d0962ab20fa0c6020000")
            },
            service_data={
                "0000fd3d-0000-1000-8000-00805f9b34fb": bytes(
                    [0, 0, 80, pairing, 0x10, 0x57, 0x98]
                )
            },
        ),
        source="local",
        connectable=True,
        time=0,
    )


@pytest.fixture
async def modern_device(
    hass: HomeAssistant, mock_entry_encrypted_factory: Callable[[str], MockConfigEntry]
) -> AsyncGenerator[switchbot.SwitchbotModernCeilingFan]:
    """Set up a Modern Ceiling Fan with polled RGB data."""
    inject_bluetooth_service_info(hass, service_info())
    entry = mock_entry_encrypted_factory("modern_ceiling_fan")
    entry.add_to_hass(hass)
    with patch(
        "switchbot.SwitchbotModernCeilingFan.get_basic_info",
        return_value={"color_light_rgb": (40, 80, 120), "firmware": 2.8},
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
        yield entry.runtime_data.device


@pytest.mark.usefixtures("modern_device")
async def test_states(hass: HomeAssistant) -> None:
    """Expose independent fan, white and RGB state."""
    fan = hass.states.get("fan.test_name")
    white = hass.states.get("light.test_name_white_light")
    color = hass.states.get("light.test_name_color_light")
    assert fan.state == STATE_ON
    assert fan.attributes["percentage"] == 42
    assert fan.attributes["preset_modes"] == [
        "normal",
        "natural",
        "sleep",
        "hurricane",
        "reverse",
    ]
    assert white.state == STATE_ON
    assert white.attributes["brightness"] == 128
    assert white.attributes["color_temp_kelvin"] == 4000
    assert white.attributes["supported_color_modes"] == ["color_temp"]
    assert color.state == STATE_ON
    assert color.attributes["brightness"] == 178
    assert color.attributes["rgb_color"] == (40, 80, 120)
    assert color.attributes["supported_color_modes"] == ["rgb"]
    assert len(hass.states.async_all("light")) == 2


@pytest.mark.parametrize(
    ("domain", "service", "entity", "method", "data", "args", "kwargs"),
    [
        ("fan", "turn_on", "fan.test_name", "turn_on", {}, (), {}),
        ("fan", "turn_off", "fan.test_name", "turn_off", {}, (), {}),
        (
            "fan",
            "set_percentage",
            "fan.test_name",
            "set_percentage",
            {"percentage": 42},
            (42,),
            {},
        ),
        (
            "fan",
            "set_preset_mode",
            "fan.test_name",
            "set_preset_mode",
            {"preset_mode": "reverse"},
            ("reverse",),
            {},
        ),
        (
            "fan",
            "oscillate",
            "fan.test_name",
            "set_oscillation",
            {"oscillating": True},
            (True,),
            {},
        ),
        (
            "light",
            "turn_on",
            "light.test_name_white_light",
            "set_main_light",
            {"brightness": 128, "color_temp_kelvin": 4000},
            (True,),
            {"brightness": 50, "color_temp": 4000},
        ),
        (
            "light",
            "turn_off",
            "light.test_name_white_light",
            "set_main_light",
            {},
            (False,),
            {},
        ),
        (
            "light",
            "turn_on",
            "light.test_name_color_light",
            "set_color_light",
            {"brightness": 128, "rgb_color": [10, 20, 30]},
            (True,),
            {"brightness": 50, "rgb": (10, 20, 30)},
        ),
        (
            "light",
            "turn_off",
            "light.test_name_color_light",
            "set_color_light",
            {},
            (False,),
            {},
        ),
        (
            "switch",
            "turn_on",
            "switch.test_name_vertical_oscillation",
            "set_vertical_oscillation",
            {},
            (True,),
            {},
        ),
    ],
)
async def test_services(
    hass: HomeAssistant,
    modern_device: switchbot.SwitchbotModernCeilingFan,
    domain: str,
    service: str,
    entity: str,
    method: str,
    data: dict,
    args: tuple,
    kwargs: dict,
) -> None:
    """Dispatch controls to the selected device function."""
    with patch.object(modern_device, method, AsyncMock(return_value=True)) as operation:
        await hass.services.async_call(
            domain, service, {ATTR_ENTITY_ID: entity, **data}, blocking=True
        )
        operation.assert_awaited_once_with(*args, **kwargs)


@pytest.mark.parametrize("pairing", [0, 1])
async def test_discovery(hass: HomeAssistant, pairing: int) -> None:
    """Discover both product identifiers and validate the encryption key."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_BLUETOOTH}, data=service_info(pairing)
    )
    assert result["step_id"] == "encrypted_choose_method"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "encrypted_key"}
    )
    assert result["step_id"] == "encrypted_key"
    with (
        patch_async_setup_entry(),
        patch(
            "switchbot.SwitchbotModernCeilingFan.verify_encryption_key",
            return_value=True,
        ) as verify,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_KEY_ID: "ff", CONF_ENCRYPTION_KEY: "ff" * 16}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "aabbccddeeff"
    assert result["data"]["sensor_type"] == "modern_ceiling_fan"
    verify.assert_awaited_once()
