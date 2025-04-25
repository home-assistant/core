"""Test Govee light local."""

from errno import EADDRINUSE, ENETDOWN
from unittest.mock import AsyncMock, MagicMock, call, patch

from govee_local_api import GoveeDevice
import pytest

from homeassistant.components.govee_light_local.const import DOMAIN
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

from .conftest import DEFAULT_CAPABILITIES, SCENE_CAPABILITIES

from tests.common import MockConfigEntry


async def test_light_known_device(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test adding a known device."""

    mock_govee_api.devices = [
        GoveeDevice(
            controller=mock_govee_api,
            ip="192.168.1.100",
            fingerprint="asdawdqwdqwd",
            sku="H615A",
            capabilities=DEFAULT_CAPABILITIES,
        )
    ]

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1

    light = hass.states.get("light.H615A")
    assert light is not None

    color_modes = light.attributes[ATTR_SUPPORTED_COLOR_MODES]
    assert set(color_modes) == {ColorMode.COLOR_TEMP, ColorMode.RGB}

    # Remove
    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("light.H615A") is None


async def test_light_unknown_device(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test adding an unknown device."""

    mock_govee_api.devices = [
        GoveeDevice(
            controller=mock_govee_api,
            ip="192.168.1.101",
            fingerprint="unkown_device",
            sku="XYZK",
            capabilities=None,
        )
    ]

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1

    light = hass.states.get("light.XYZK")
    assert light is not None

    assert light.attributes[ATTR_SUPPORTED_COLOR_MODES] == [ColorMode.ONOFF]


async def test_light_remove(hass: HomeAssistant, mock_govee_api: AsyncMock) -> None:
    """Test remove device."""

    mock_govee_api.devices = [
        GoveeDevice(
            controller=mock_govee_api,
            ip="192.168.1.100",
            fingerprint="asdawdqwdqwd1",
            sku="H615A",
            capabilities=DEFAULT_CAPABILITIES,
        )
    ]

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("light.H615A") is not None

    # Remove 1
    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0


async def test_light_setup_retry(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test setup retry."""

    mock_govee_api.devices = []

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.govee_light_local.DISCOVERY_TIMEOUT",
        0,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_light_setup_retry_eaddrinuse(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test retry on address already in use."""

    mock_govee_api.start.side_effect = OSError()
    mock_govee_api.start.side_effect.errno = EADDRINUSE
    mock_govee_api.devices = [
        GoveeDevice(
            controller=mock_govee_api,
            ip="192.168.1.100",
            fingerprint="asdawdqwdqwd",
            sku="H615A",
            capabilities=DEFAULT_CAPABILITIES,
        )
    ]

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_light_setup_error(
    hass: HomeAssistant, mock_govee_api: AsyncMock
) -> None:
    """Test setup error."""

    mock_govee_api.start.side_effect = OSError()
    mock_govee_api.start.side_effect.errno = ENETDOWN
    mock_govee_api.devices = [
        GoveeDevice(
            controller=mock_govee_api,
            ip="192.168.1.100",
            fingerprint="asdawdqwdqwd",
            sku="H615A",
            capabilities=DEFAULT_CAPABILITIES,
        )
    ]

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_light_on_off(hass: HomeAssistant, mock_govee_api: MagicMock) -> None:
    """Test light on and then off."""

    mock_govee_api.devices = [
        GoveeDevice(
            controller=mock_govee_api,
            ip="192.168.1.100",
            fingerprint="asdawdqwdqwd",
            sku="H615A",
            capabilities=DEFAULT_CAPABILITIES,
        )
    ]

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "off"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": light.entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "on"
    mock_govee_api.turn_on_off.assert_awaited_with(mock_govee_api.devices[0], True)

    # Turn off
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {"entity_id": light.entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "off"
    mock_govee_api.turn_on_off.assert_awaited_with(mock_govee_api.devices[0], False)


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
        (ATTR_EFFECT, "sunrise", "set_scene", ["sunrise"], {}),
    ],
)
async def test_turn_on_call_order(
    hass: HomeAssistant,
    mock_govee_api: MagicMock,
    attribute: str,
    value: str | int | list[int],
    mock_call: str,
    mock_call_args: list[str],
    mock_call_kwargs: dict[str, any],
) -> None:
    """Test that turn_on is called after set_brightness/set_color/set_preset."""
    mock_govee_api.devices = [
        GoveeDevice(
            controller=mock_govee_api,
            ip="192.168.1.100",
            fingerprint="asdawdqwdqwd",
            sku="H615A",
            capabilities=SCENE_CAPABILITIES,
        )
    ]

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "off"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": light.entity_id, ATTR_BRIGHTNESS_PCT: 50, attribute: value},
        blocking=True,
    )
    await hass.async_block_till_done()

    mock_govee_api.assert_has_calls(
        [
            call.set_brightness(mock_govee_api.devices[0], 50),
            getattr(call, mock_call)(
                mock_govee_api.devices[0], *mock_call_args, **mock_call_kwargs
            ),
            call.turn_on_off(mock_govee_api.devices[0], True),
        ]
    )


async def test_light_brightness(hass: HomeAssistant, mock_govee_api: MagicMock) -> None:
    """Test changing brightness."""
    mock_govee_api.devices = [
        GoveeDevice(
            controller=mock_govee_api,
            ip="192.168.1.100",
            fingerprint="asdawdqwdqwd",
            sku="H615A",
            capabilities=DEFAULT_CAPABILITIES,
        )
    ]

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "off"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": light.entity_id, "brightness_pct": 50},
        blocking=True,
    )
    await hass.async_block_till_done()

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "on"
    mock_govee_api.set_brightness.assert_awaited_with(mock_govee_api.devices[0], 50)
    assert light.attributes[ATTR_BRIGHTNESS] == 127

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": light.entity_id, ATTR_BRIGHTNESS: 255},
        blocking=True,
    )
    await hass.async_block_till_done()

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "on"
    assert light.attributes[ATTR_BRIGHTNESS] == 255
    mock_govee_api.set_brightness.assert_awaited_with(mock_govee_api.devices[0], 100)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": light.entity_id, ATTR_BRIGHTNESS: 255},
        blocking=True,
    )
    await hass.async_block_till_done()

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "on"
    assert light.attributes[ATTR_BRIGHTNESS] == 255
    mock_govee_api.set_brightness.assert_awaited_with(mock_govee_api.devices[0], 100)


async def test_light_color(hass: HomeAssistant, mock_govee_api: MagicMock) -> None:
    """Test changing brightness."""
    mock_govee_api.devices = [
        GoveeDevice(
            controller=mock_govee_api,
            ip="192.168.1.100",
            fingerprint="asdawdqwdqwd",
            sku="H615A",
            capabilities=DEFAULT_CAPABILITIES,
        )
    ]

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "off"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": light.entity_id, ATTR_RGB_COLOR: [100, 255, 50]},
        blocking=True,
    )
    await hass.async_block_till_done()

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "on"
    assert light.attributes[ATTR_RGB_COLOR] == (100, 255, 50)
    assert light.attributes["color_mode"] == ColorMode.RGB

    mock_govee_api.set_color.assert_awaited_with(
        mock_govee_api.devices[0], rgb=(100, 255, 50), temperature=None
    )

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": light.entity_id, "kelvin": 4400},
        blocking=True,
    )
    await hass.async_block_till_done()

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "on"
    assert light.attributes["color_temp_kelvin"] == 4400
    assert light.attributes["color_mode"] == ColorMode.COLOR_TEMP

    mock_govee_api.set_color.assert_awaited_with(
        mock_govee_api.devices[0], rgb=None, temperature=4400
    )


async def test_scene_on(hass: HomeAssistant, mock_govee_api: MagicMock) -> None:
    """Test turning on scene."""

    mock_govee_api.devices = [
        GoveeDevice(
            controller=mock_govee_api,
            ip="192.168.1.100",
            fingerprint="asdawdqwdqwd",
            sku="H615A",
            capabilities=SCENE_CAPABILITIES,
        )
    ]

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "off"

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": light.entity_id, ATTR_EFFECT: "sunrise"},
        blocking=True,
    )
    await hass.async_block_till_done()

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "on"
    assert light.attributes[ATTR_EFFECT] == "sunrise"
    mock_govee_api.turn_on_off.assert_awaited_with(mock_govee_api.devices[0], True)


async def test_scene_restore_rgb(
    hass: HomeAssistant, mock_govee_api: MagicMock
) -> None:
    """Test restore rgb color."""

    mock_govee_api.devices = [
        GoveeDevice(
            controller=mock_govee_api,
            ip="192.168.1.100",
            fingerprint="asdawdqwdqwd",
            sku="H615A",
            capabilities=SCENE_CAPABILITIES,
        )
    ]

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1

    initial_color = (12, 34, 56)
    light = hass.states.get("light.H615A")
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

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "on"
    assert light.attributes[ATTR_RGB_COLOR] == initial_color
    assert light.attributes[ATTR_BRIGHTNESS] == 255
    mock_govee_api.turn_on_off.assert_awaited_with(mock_govee_api.devices[0], True)

    # Activate scene
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": light.entity_id, ATTR_EFFECT: "sunrise"},
        blocking=True,
    )
    await hass.async_block_till_done()

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "on"
    assert light.attributes[ATTR_EFFECT] == "sunrise"
    mock_govee_api.turn_on_off.assert_awaited_with(mock_govee_api.devices[0], True)

    # Deactivate scene
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": light.entity_id, ATTR_EFFECT: "none"},
        blocking=True,
    )
    await hass.async_block_till_done()

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "on"
    assert light.attributes[ATTR_EFFECT] is None
    assert light.attributes[ATTR_RGB_COLOR] == initial_color
    assert light.attributes[ATTR_BRIGHTNESS] == 255


async def test_scene_restore_temperature(
    hass: HomeAssistant, mock_govee_api: MagicMock
) -> None:
    """Test restore color temperature."""

    mock_govee_api.devices = [
        GoveeDevice(
            controller=mock_govee_api,
            ip="192.168.1.100",
            fingerprint="asdawdqwdqwd",
            sku="H615A",
            capabilities=SCENE_CAPABILITIES,
        )
    ]

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1

    initial_color = 3456
    light = hass.states.get("light.H615A")
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

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "on"
    assert light.attributes["color_temp_kelvin"] == initial_color
    mock_govee_api.turn_on_off.assert_awaited_with(mock_govee_api.devices[0], True)

    # Activate scene
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": light.entity_id, ATTR_EFFECT: "sunrise"},
        blocking=True,
    )
    await hass.async_block_till_done()

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "on"
    assert light.attributes[ATTR_EFFECT] == "sunrise"
    mock_govee_api.set_scene.assert_awaited_with(mock_govee_api.devices[0], "sunrise")

    # Deactivate scene
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": light.entity_id, ATTR_EFFECT: "none"},
        blocking=True,
    )
    await hass.async_block_till_done()

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "on"
    assert light.attributes[ATTR_EFFECT] is None
    assert light.attributes["color_temp_kelvin"] == initial_color


async def test_scene_none(hass: HomeAssistant, mock_govee_api: MagicMock) -> None:
    """Test turn on 'none' scene."""

    mock_govee_api.devices = [
        GoveeDevice(
            controller=mock_govee_api,
            ip="192.168.1.100",
            fingerprint="asdawdqwdqwd",
            sku="H615A",
            capabilities=SCENE_CAPABILITIES,
        )
    ]

    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1

    initial_color = (12, 34, 56)
    light = hass.states.get("light.H615A")
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

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "on"
    assert light.attributes[ATTR_RGB_COLOR] == initial_color
    assert light.attributes[ATTR_BRIGHTNESS] == 255
    mock_govee_api.turn_on_off.assert_awaited_with(mock_govee_api.devices[0], True)

    # Activate scene
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {"entity_id": light.entity_id, ATTR_EFFECT: "none"},
        blocking=True,
    )
    await hass.async_block_till_done()
    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "on"
    assert light.attributes[ATTR_EFFECT] is None
    mock_govee_api.set_scene.assert_not_called()
