"""Test DayBetter light local."""

from errno import EADDRINUSE, ENETDOWN
from unittest.mock import AsyncMock, MagicMock, call, patch

from daybetter_local_api import DayBetterDevice
import pytest

from homeassistant.components.daybetter_light_local.const import DOMAIN
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    DOMAIN as LIGHT_DOMAIN,
    ColorMode,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .conftest import DEFAULT_CAPABILITIES, SCENE_CAPABILITIES

from tests.common import MockConfigEntry


async def test_light_known_device(
    hass: HomeAssistant, mock_DayBetter_api: AsyncMock
) -> None:
    """Test adding a known device."""

    mock_DayBetter_api.devices = [
        DayBetterDevice(
            controller=mock_DayBetter_api,
            ip="192.168.1.100",
            fingerprint="hhhhhhhhhhhh",
            sku="P076",
            capabilities=DEFAULT_CAPABILITIES,
        )
    ]
    with patch(
        "homeassistant.components.daybetter_light_local.coordinator.DayBetterController",
        return_value=mock_DayBetter_api,
    ):
        entry = MockConfigEntry(domain=DOMAIN)
        entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert len(hass.states.async_all()) == 1

        light = hass.states.get("light.P076")
        assert light is not None

        color_modes = light.attributes[ATTR_SUPPORTED_COLOR_MODES]
        assert set(color_modes) == {ColorMode.COLOR_TEMP, ColorMode.RGB}

        # Remove
        assert await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get("light.P076") is None


async def test_light_unknown_device(
    hass: HomeAssistant, mock_DayBetter_api: AsyncMock
) -> None:
    """Test adding an unknown device."""

    mock_DayBetter_api.devices = [
        DayBetterDevice(
            controller=mock_DayBetter_api,
            ip="192.168.1.201",
            fingerprint="unkown_device",
            sku="XYZK",
            capabilities=None,
        )
    ]
    with patch(
        "homeassistant.components.daybetter_light_local.coordinator.DayBetterController",
        return_value=mock_DayBetter_api,
    ):
        entry = MockConfigEntry(domain=DOMAIN)
        entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert len(hass.states.async_all()) == 1

        light = hass.states.get("light.XYZK")
        assert light is not None

        assert light.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.ONOFF]


async def test_light_remove(hass: HomeAssistant, mock_DayBetter_api: AsyncMock) -> None:
    """Test remove device."""

    mock_DayBetter_api.devices = [
        DayBetterDevice(
            controller=mock_DayBetter_api,
            ip="192.168.1.100",
            fingerprint="hhhhhhhhhhhhh",
            sku="P076",
            capabilities=DEFAULT_CAPABILITIES,
        )
    ]
    with patch(
        "homeassistant.components.daybetter_light_local.coordinator.DayBetterController",
        return_value=mock_DayBetter_api,
    ):
        entry = MockConfigEntry(domain=DOMAIN)
        entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get("light.P076") is not None

        # Remove 1
        assert await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()
        assert len(hass.states.async_all()) == 0


async def test_light_setup_retry(
    hass: HomeAssistant, mock_DayBetter_api: AsyncMock
) -> None:
    """Test setup retry."""

    # 确保协调器的 devices 属性返回空列表
    mock_DayBetter_api.devices = []

    with (
        patch(
            "homeassistant.components.daybetter_light_local.coordinator.DayBetterController",
            return_value=mock_DayBetter_api,
        ),
        patch(
            "homeassistant.components.daybetter_light_local.coordinator.DayBetterLocalApiCoordinator._async_update_data",
            return_value=[],  # 确保更新数据也返回空
        ),
        patch(
            "homeassistant.components.daybetter_light_local.coordinator.DayBetterLocalApiCoordinator.devices",
            return_value=[],  # 确保设备列表为空
        ),
    ):
        entry = MockConfigEntry(domain=DOMAIN, data={"host": "192.168.1.100"})
        entry.add_to_hass(hass)

        # 现在应该抛出 ConfigEntryNotReady 异常
        with pytest.raises(ConfigEntryNotReady, match="No DayBetter devices found"):
            await hass.config_entries.async_setup(entry.entry_id)


async def test_light_setup_retry_eaddrinuse(
    hass: HomeAssistant, mock_DayBetter_api: AsyncMock
) -> None:
    """Test retry on address already in use."""

    mock_DayBetter_api.start.side_effect = OSError()
    mock_DayBetter_api.start.side_effect.errno = EADDRINUSE
    mock_DayBetter_api.devices = [
        DayBetterDevice(
            controller=mock_DayBetter_api,
            ip="192.168.1.100",
            fingerprint="hhhhhhhhhhhhh",
            sku="P076",
            capabilities=DEFAULT_CAPABILITIES,
        )
    ]
    with patch(
        "homeassistant.components.daybetter_light_local.coordinator.DayBetterController",
        return_value=mock_DayBetter_api,
    ):
        entry = MockConfigEntry(domain=DOMAIN)
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_light_setup_error(
    hass: HomeAssistant, mock_DayBetter_api: AsyncMock
) -> None:
    """Test setup error."""

    mock_DayBetter_api.start.side_effect = OSError()
    mock_DayBetter_api.start.side_effect.errno = ENETDOWN
    mock_DayBetter_api.devices = [
        DayBetterDevice(
            controller=mock_DayBetter_api,
            ip="192.168.1.100",
            fingerprint="hhhhhhhhhhhhh",
            sku="P076",
            capabilities=DEFAULT_CAPABILITIES,
        )
    ]
    with patch(
        "homeassistant.components.daybetter_light_local.coordinator.DayBetterController",
        return_value=mock_DayBetter_api,
    ):
        entry = MockConfigEntry(domain=DOMAIN)
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_light_on_off(hass: HomeAssistant, mock_DayBetter_api: MagicMock) -> None:
    """Test light on and then off."""

    mock_DayBetter_api.devices = [
        DayBetterDevice(
            controller=mock_DayBetter_api,
            ip="192.168.1.100",
            fingerprint="hhhhhhhhhhhhh",
            sku="P076",
            capabilities=DEFAULT_CAPABILITIES,
        )
    ]
    with patch(
        "homeassistant.components.daybetter_light_local.coordinator.DayBetterController",
        return_value=mock_DayBetter_api,
    ):
        entry = MockConfigEntry(domain=DOMAIN)
        entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert len(hass.states.async_all()) == 1

        light = hass.states.get("light.P076")
        assert light is not None
        assert light.state == "off"

        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {"entity_id": light.entity_id},
            blocking=True,
        )
        await hass.async_block_till_done()

        light = hass.states.get("light.P076")
        assert light is not None
        assert light.state == "on"
        mock_DayBetter_api.turn_on_off.assert_awaited_with(
            mock_DayBetter_api.devices[0], True
        )

        # Turn off
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {"entity_id": light.entity_id},
            blocking=True,
        )
        await hass.async_block_till_done()

        light = hass.states.get("light.P076")
        assert light is not None
        assert light.state == "off"
        mock_DayBetter_api.turn_on_off.assert_awaited_with(
            mock_DayBetter_api.devices[0], False
        )


@pytest.mark.parametrize(
    ("attribute", "value", "mock_call", "mock_call_args", "mock_call_kwargs"),
    [
        (
            ATTR_RGB_COLOR,
            [100, 255, 50],
            "set_color",
            [],
            {"temperature": None, "rgb": (100, 255, 50)},
        ),
        (
            ATTR_COLOR_TEMP_KELVIN,
            4400,
            "set_color",
            [],
            {"temperature": 4400, "rgb": None},
        ),
        (ATTR_EFFECT, "christmas", "set_scene", ["christmas"], {}),
    ],
)
async def test_turn_on_call_order(
    hass: HomeAssistant,
    mock_DayBetter_api: MagicMock,
    attribute: str,
    value: str | int | list[int],
    mock_call: str,
    mock_call_args: list[str],
    mock_call_kwargs: dict[str, any],
) -> None:
    """Test that turn_on is called after set_brightness/set_color/set_preset."""
    mock_DayBetter_api.devices = [
        DayBetterDevice(
            controller=mock_DayBetter_api,
            ip="192.168.1.100",
            fingerprint="hhhhhhhhhhhhh",
            sku="P076",
            capabilities=SCENE_CAPABILITIES,
        )
    ]
    with patch(
        "homeassistant.components.daybetter_light_local.coordinator.DayBetterController",
        return_value=mock_DayBetter_api,
    ):
        entry = MockConfigEntry(domain=DOMAIN)
        entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert len(hass.states.async_all()) == 1

        light = hass.states.get("light.P076")
        assert light is not None
        assert light.state == "off"

        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {"entity_id": light.entity_id, ATTR_BRIGHTNESS_PCT: 50, attribute: value},
            blocking=True,
        )
        await hass.async_block_till_done()

        mock_DayBetter_api.assert_has_calls(
            [
                call.set_brightness(mock_DayBetter_api.devices[0], 50),
                getattr(call, mock_call)(
                    mock_DayBetter_api.devices[0], *mock_call_args, **mock_call_kwargs
                ),
                call.turn_on_off(mock_DayBetter_api.devices[0], True),
            ]
        )


async def test_light_brightness(
    hass: HomeAssistant, mock_DayBetter_api: MagicMock
) -> None:
    """Test changing brightness."""
    mock_DayBetter_api.devices = [
        DayBetterDevice(
            controller=mock_DayBetter_api,
            ip="192.168.1.100",
            fingerprint="hhhhhhhhhhhhhh",
            sku="P076",
            capabilities=DEFAULT_CAPABILITIES,
        )
    ]
    with patch(
        "homeassistant.components.daybetter_light_local.coordinator.DayBetterController",
        return_value=mock_DayBetter_api,
    ):
        entry = MockConfigEntry(domain=DOMAIN)
        entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert len(hass.states.async_all()) == 1

        light = hass.states.get("light.P076")
        assert light is not None
        assert light.state == "off"

        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {"entity_id": light.entity_id, "brightness_pct": 50},
            blocking=True,
        )
        await hass.async_block_till_done()

        light = hass.states.get("light.P076")
        assert light is not None
        assert light.state == "on"
        mock_DayBetter_api.set_brightness.assert_awaited_with(
            mock_DayBetter_api.devices[0], 50
        )
        assert light.attributes[ATTR_BRIGHTNESS] == 127

        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {"entity_id": light.entity_id, ATTR_BRIGHTNESS: 255},
            blocking=True,
        )
        await hass.async_block_till_done()

        light = hass.states.get("light.P076")
        assert light is not None
        assert light.state == "on"
        assert light.attributes[ATTR_BRIGHTNESS] == 255
        mock_DayBetter_api.set_brightness.assert_awaited_with(
            mock_DayBetter_api.devices[0], 100
        )

        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {"entity_id": light.entity_id, ATTR_BRIGHTNESS: 255},
            blocking=True,
        )
        await hass.async_block_till_done()

        light = hass.states.get("light.P076")
        assert light is not None
        assert light.state == "on"
        assert light.attributes[ATTR_BRIGHTNESS] == 255
        mock_DayBetter_api.set_brightness.assert_awaited_with(
            mock_DayBetter_api.devices[0], 100
        )


async def test_light_color(hass: HomeAssistant, mock_DayBetter_api: MagicMock) -> None:
    """Test changing brightness."""
    mock_DayBetter_api.devices = [
        DayBetterDevice(
            controller=mock_DayBetter_api,
            ip="192.168.1.100",
            fingerprint="hhhhhhhhhhhhhh",
            sku="P076",
            capabilities=DEFAULT_CAPABILITIES,
        )
    ]
    with patch(
        "homeassistant.components.daybetter_light_local.coordinator.DayBetterController",
        return_value=mock_DayBetter_api,
    ):
        entry = MockConfigEntry(domain=DOMAIN)
        entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert len(hass.states.async_all()) == 1

        light = hass.states.get("light.P076")
        assert light is not None
        assert light.state == "off"

        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {"entity_id": light.entity_id, ATTR_RGB_COLOR: [100, 255, 50]},
            blocking=True,
        )
        await hass.async_block_till_done()

        light = hass.states.get("light.P076")
        assert light is not None
        assert light.state == "on"
        assert light.attributes[ATTR_RGB_COLOR] == (100, 255, 50)
        assert light.attributes["color_mode"] == ColorMode.RGB

        mock_DayBetter_api.set_color.assert_awaited_with(
            mock_DayBetter_api.devices[0], rgb=(100, 255, 50), temperature=None
        )

        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {"entity_id": light.entity_id, "kelvin": 4400},
            blocking=True,
        )
        await hass.async_block_till_done()

        light = hass.states.get("light.P076")
        assert light is not None
        assert light.state == "on"
        assert light.attributes["color_temp_kelvin"] == 4400
        assert light.attributes["color_mode"] == ColorMode.COLOR_TEMP

        mock_DayBetter_api.set_color.assert_awaited_with(
            mock_DayBetter_api.devices[0], rgb=None, temperature=4400
        )


async def test_scene_on(hass: HomeAssistant, mock_DayBetter_api: MagicMock) -> None:
    """Test turning on scene."""

    mock_DayBetter_api.devices = [
        DayBetterDevice(
            controller=mock_DayBetter_api,
            ip="192.168.1.100",
            fingerprint="hhhhhhhhhhhhhh",
            sku="P076",
            capabilities=SCENE_CAPABILITIES,
        )
    ]
    with patch(
        "homeassistant.components.daybetter_light_local.coordinator.DayBetterController",
        return_value=mock_DayBetter_api,
    ):
        entry = MockConfigEntry(domain=DOMAIN)
        entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert len(hass.states.async_all()) == 1

        light = hass.states.get("light.P076")
        assert light is not None
        assert light.state == "off"

        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {"entity_id": light.entity_id, ATTR_EFFECT: "christmas"},
            blocking=True,
        )
        await hass.async_block_till_done()

        light = hass.states.get("light.P076")
        assert light is not None
        assert light.state == "on"
        assert light.attributes[ATTR_EFFECT] == "christmas"
        mock_DayBetter_api.turn_on_off.assert_awaited_with(
            mock_DayBetter_api.devices[0], True
        )


async def test_scene_restore_rgb(
    hass: HomeAssistant, mock_DayBetter_api: MagicMock
) -> None:
    """Test restore rgb color."""

    mock_DayBetter_api.devices = [
        DayBetterDevice(
            controller=mock_DayBetter_api,
            ip="192.168.1.100",
            fingerprint="asdawdqwdqwd",
            sku="P076",
            capabilities=SCENE_CAPABILITIES,
        )
    ]
    with patch(
        "homeassistant.components.daybetter_light_local.coordinator.DayBetterController",
        return_value=mock_DayBetter_api,
    ):
        entry = MockConfigEntry(domain=DOMAIN)
        entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert len(hass.states.async_all()) == 1

        initial_color = (12, 34, 56)
        light = hass.states.get("light.P076")
        assert light is not None
        assert light.state == "off"

        # Set initial color
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {"entity_id": light.entity_id, ATTR_RGB_COLOR: initial_color},
            blocking=True,
        )
        await hass.async_block_till_done()
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {"entity_id": light.entity_id, ATTR_BRIGHTNESS: 255},
            blocking=True,
        )
        await hass.async_block_till_done()

        light = hass.states.get("light.P076")
        assert light is not None
        assert light.state == "on"
        assert light.attributes[ATTR_RGB_COLOR] == initial_color
        assert light.attributes[ATTR_BRIGHTNESS] == 255
        mock_DayBetter_api.turn_on_off.assert_awaited_with(
            mock_DayBetter_api.devices[0], True
        )

        # Activate scene
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {"entity_id": light.entity_id, ATTR_EFFECT: "christmas"},
            blocking=True,
        )
        await hass.async_block_till_done()

        light = hass.states.get("light.P076")
        assert light is not None
        assert light.state == "on"
        assert light.attributes[ATTR_EFFECT] == "christmas"
        mock_DayBetter_api.turn_on_off.assert_awaited_with(
            mock_DayBetter_api.devices[0], True
        )

        # Deactivate scene
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {"entity_id": light.entity_id, ATTR_EFFECT: "none"},
            blocking=True,
        )
        await hass.async_block_till_done()

        light = hass.states.get("light.P076")
        assert light is not None
        assert light.state == "on"
        assert light.attributes[ATTR_EFFECT] is None
        assert light.attributes[ATTR_RGB_COLOR] == initial_color
        assert light.attributes[ATTR_BRIGHTNESS] == 255


async def test_scene_restore_temperature(
    hass: HomeAssistant, mock_DayBetter_api: MagicMock
) -> None:
    """Test restore color temperature."""

    mock_DayBetter_api.devices = [
        DayBetterDevice(
            controller=mock_DayBetter_api,
            ip="192.168.1.100",
            fingerprint="asdawdqwdqwd",
            sku="P076",
            capabilities=SCENE_CAPABILITIES,
        )
    ]
    with patch(
        "homeassistant.components.daybetter_light_local.coordinator.DayBetterController",
        return_value=mock_DayBetter_api,
    ):
        entry = MockConfigEntry(domain=DOMAIN)
        entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert len(hass.states.async_all()) == 1

        initial_color = 3456
        light = hass.states.get("light.P076")
        assert light is not None
        assert light.state == "off"

        # Set initial color
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {"entity_id": light.entity_id, "color_temp_kelvin": initial_color},
            blocking=True,
        )
        await hass.async_block_till_done()

        light = hass.states.get("light.P076")
        assert light is not None
        assert light.state == "on"
        assert light.attributes["color_temp_kelvin"] == initial_color
        mock_DayBetter_api.turn_on_off.assert_awaited_with(
            mock_DayBetter_api.devices[0], True
        )

        # Activate scene
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {"entity_id": light.entity_id, ATTR_EFFECT: "christmas"},
            blocking=True,
        )
        await hass.async_block_till_done()

        light = hass.states.get("light.P076")
        assert light is not None
        assert light.state == "on"
        assert light.attributes[ATTR_EFFECT] == "christmas"
        mock_DayBetter_api.set_scene.assert_awaited_with(
            mock_DayBetter_api.devices[0], "christmas"
        )

        # Deactivate scene
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {"entity_id": light.entity_id, ATTR_EFFECT: "none"},
            blocking=True,
        )
        await hass.async_block_till_done()

        light = hass.states.get("light.P076")
        assert light is not None
        assert light.state == "on"
        assert light.attributes[ATTR_EFFECT] is None
        assert light.attributes["color_temp_kelvin"] == initial_color


async def test_scene_none(hass: HomeAssistant, mock_DayBetter_api: MagicMock) -> None:
    """Test turn on 'none' scene."""

    mock_DayBetter_api.devices = [
        DayBetterDevice(
            controller=mock_DayBetter_api,
            ip="192.168.1.100",
            fingerprint="hhhhhhhhhhhhhhh",
            sku="P076",
            capabilities=SCENE_CAPABILITIES,
        )
    ]
    with patch(
        "homeassistant.components.daybetter_light_local.coordinator.DayBetterController",
        return_value=mock_DayBetter_api,
    ):
        entry = MockConfigEntry(domain=DOMAIN)
        entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert len(hass.states.async_all()) == 1

        initial_color = (12, 34, 56)
        light = hass.states.get("light.P076")
        assert light is not None
        assert light.state == "off"

        # Set initial color
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {"entity_id": light.entity_id, ATTR_RGB_COLOR: initial_color},
            blocking=True,
        )
        await hass.async_block_till_done()
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {"entity_id": light.entity_id, ATTR_BRIGHTNESS: 255},
            blocking=True,
        )
        await hass.async_block_till_done()

        light = hass.states.get("light.P076")
        assert light is not None
        assert light.state == "on"
        assert light.attributes[ATTR_RGB_COLOR] == initial_color
        assert light.attributes[ATTR_BRIGHTNESS] == 255
        mock_DayBetter_api.turn_on_off.assert_awaited_with(
            mock_DayBetter_api.devices[0], True
        )

        # Activate scene
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {"entity_id": light.entity_id, ATTR_EFFECT: "none"},
            blocking=True,
        )
        await hass.async_block_till_done()
        light = hass.states.get("light.P076")
        assert light is not None
        assert light.state == "on"
        assert light.attributes[ATTR_EFFECT] is None
        mock_DayBetter_api.set_scene.assert_not_called()
