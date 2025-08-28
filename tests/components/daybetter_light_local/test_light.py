"""Test DayBetter light local integration."""

from errno import EADDRINUSE, ENETDOWN
from unittest.mock import AsyncMock, MagicMock, PropertyMock, call, patch

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

from .conftest import DEFAULT_CAPABILITIES, SCENE_CAPABILITIES

from tests.common import MockConfigEntry

CONTROLLER_PATH = (
    "homeassistant.components.daybetter_light_local.coordinator.DayBetterController"
)


# ----------------------------- Helper -----------------------------
def create_mock_device(
    controller,
    ip="192.168.1.100",
    fingerprint="hhhhhhhhhhhhh",
    sku="P076",
    capabilities=DEFAULT_CAPABILITIES,
):
    """Create a mock DayBetterDevice for testing."""
    return DayBetterDevice(
        controller=controller,
        ip=ip,
        fingerprint=fingerprint,
        sku=sku,
        capabilities=capabilities,
    )


# ----------------------------- Tests -----------------------------
async def test_light_known_device(
    hass: HomeAssistant, mock_DayBetter_api: AsyncMock
) -> None:
    """Test adding a known device."""

    device = create_mock_device(mock_DayBetter_api, capabilities=DEFAULT_CAPABILITIES)
    mock_DayBetter_api.devices = [device]

    mock_DayBetter_api.start = AsyncMock()
    mock_DayBetter_api.async_refresh = AsyncMock()

    with patch(CONTROLLER_PATH, return_value=mock_DayBetter_api):
        entry = MockConfigEntry(domain=DOMAIN, data={"host": "192.168.1.100"})
        entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

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

    device = create_mock_device(
        mock_DayBetter_api,
        ip="192.168.1.201",
        fingerprint="unknown_device",
        sku="XYZK",
        capabilities=DEFAULT_CAPABILITIES,
    )
    mock_DayBetter_api.devices = [device]

    mock_DayBetter_api.start = AsyncMock()
    mock_DayBetter_api.async_refresh = AsyncMock()

    with patch(CONTROLLER_PATH, return_value=mock_DayBetter_api):
        entry = MockConfigEntry(domain=DOMAIN, data={"host": "192.168.1.201"})
        entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert len(hass.states.async_all()) == 1

        light = hass.states.get("light.XYZK")
        assert light is not None
        assert set(light.attributes[ATTR_SUPPORTED_COLOR_MODES]) == {
            ColorMode.COLOR_TEMP,
            ColorMode.RGB,
        }


async def test_light_remove(hass: HomeAssistant, mock_DayBetter_api: AsyncMock) -> None:
    """Test removing a device."""

    device = create_mock_device(mock_DayBetter_api, capabilities=DEFAULT_CAPABILITIES)
    mock_DayBetter_api.devices = [device]

    mock_DayBetter_api.start = AsyncMock()
    mock_DayBetter_api.async_refresh = AsyncMock()

    with patch(CONTROLLER_PATH, return_value=mock_DayBetter_api):
        entry = MockConfigEntry(domain=DOMAIN, data={"host": "192.168.1.100"})
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get("light.P076") is not None

        # Remove
        await hass.config_entries.async_remove(entry.entry_id)
        await hass.async_block_till_done()
        assert len(hass.states.async_all()) == 0


async def test_light_setup_retry(
    hass: HomeAssistant, mock_DayBetter_api: AsyncMock
) -> None:
    """Test setup retry when no devices are found."""

    mock_DayBetter_api.devices = []
    mock_DayBetter_api.start = AsyncMock()
    mock_DayBetter_api.async_refresh = AsyncMock()

    with (
        patch(CONTROLLER_PATH, return_value=mock_DayBetter_api),
        patch(
            "homeassistant.components.daybetter_light_local.coordinator.DayBetterLocalApiCoordinator._async_update_data",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "homeassistant.components.daybetter_light_local.coordinator.DayBetterLocalApiCoordinator.devices",
            new_callable=PropertyMock,
            return_value=[],
        ),
    ):
        entry = MockConfigEntry(domain=DOMAIN, data={"host": "192.168.1.100"})
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_light_setup_retry_eaddrinuse(
    hass: HomeAssistant, mock_DayBetter_api: AsyncMock
) -> None:
    """Test setup retry on address already in use."""

    mock_DayBetter_api.devices = [
        create_mock_device(mock_DayBetter_api, capabilities=DEFAULT_CAPABILITIES)
    ]
    mock_DayBetter_api.start = AsyncMock(
        side_effect=OSError(EADDRINUSE, "Address in use")
    )

    with patch(CONTROLLER_PATH, return_value=mock_DayBetter_api):
        entry = MockConfigEntry(domain=DOMAIN, data={"host": "192.168.1.100"})
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_light_setup_error(
    hass: HomeAssistant, mock_DayBetter_api: AsyncMock
) -> None:
    """Test setup failure due to network down."""

    mock_DayBetter_api.devices = [
        create_mock_device(mock_DayBetter_api, capabilities=DEFAULT_CAPABILITIES)
    ]
    mock_DayBetter_api.start = AsyncMock(side_effect=OSError(ENETDOWN, "Network down"))

    with patch(CONTROLLER_PATH, return_value=mock_DayBetter_api):
        entry = MockConfigEntry(domain=DOMAIN, data={"host": "192.168.1.100"})
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_light_on_off(hass: HomeAssistant, mock_DayBetter_api: MagicMock) -> None:
    """Test turning light on and off."""

    device = create_mock_device(mock_DayBetter_api, capabilities=DEFAULT_CAPABILITIES)
    mock_DayBetter_api.devices = [device]

    mock_DayBetter_api.start = AsyncMock()
    mock_DayBetter_api.async_refresh = AsyncMock()
    mock_DayBetter_api.turn_on_off = AsyncMock()

    with patch(CONTROLLER_PATH, return_value=mock_DayBetter_api):
        entry = MockConfigEntry(domain=DOMAIN, data={"host": "192.168.1.100"})
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
            {"rgb": (100, 255, 50), "temperature": None},
        ),
        (
            ATTR_COLOR_TEMP_KELVIN,
            4400,
            "set_color",
            [],
            {"rgb": None, "temperature": 4400},
        ),
        (ATTR_EFFECT, "christmas", "set_scene", ["christmas"], {}),
    ],
)
async def test_turn_on_call_order(
    hass: HomeAssistant,
    mock_DayBetter_api: AsyncMock,
    attribute: str,
    value,
    mock_call: str,
    mock_call_args,
    mock_call_kwargs,
) -> None:
    """Test turn_on calls correct methods in order."""

    device = create_mock_device(mock_DayBetter_api, capabilities=SCENE_CAPABILITIES)
    mock_DayBetter_api.devices = [device]

    mock_DayBetter_api.start = AsyncMock()
    mock_DayBetter_api.async_refresh = AsyncMock()
    mock_DayBetter_api.set_brightness = AsyncMock()
    mock_DayBetter_api.set_color = AsyncMock()
    mock_DayBetter_api.set_scene = AsyncMock()
    mock_DayBetter_api.turn_on_off = AsyncMock()

    with patch(CONTROLLER_PATH, return_value=mock_DayBetter_api):
        entry = MockConfigEntry(domain=DOMAIN, data={"host": "192.168.1.100"})
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


# ----------------------------- Brightness Tests -----------------------------
async def test_light_brightness(
    hass: HomeAssistant, mock_DayBetter_api: AsyncMock
) -> None:
    """Test changing brightness."""
    device = create_mock_device(mock_DayBetter_api, capabilities=DEFAULT_CAPABILITIES)
    mock_DayBetter_api.devices = [device]

    mock_DayBetter_api.start = AsyncMock()
    mock_DayBetter_api.set_brightness = AsyncMock()
    mock_DayBetter_api.turn_on_off = AsyncMock()

    with patch(CONTROLLER_PATH, return_value=mock_DayBetter_api):
        entry = MockConfigEntry(domain=DOMAIN, data={"host": "192.168.1.100"})
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

        # Turn on with max brightness
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


# ----------------------------- Color Tests -----------------------------
async def test_light_color(hass: HomeAssistant, mock_DayBetter_api: AsyncMock) -> None:
    """Test setting RGB and color temperature."""
    device = create_mock_device(mock_DayBetter_api, capabilities=DEFAULT_CAPABILITIES)
    mock_DayBetter_api.devices = [device]

    mock_DayBetter_api.start = AsyncMock()
    mock_DayBetter_api.set_color = AsyncMock()
    mock_DayBetter_api.turn_on_off = AsyncMock()

    with patch(CONTROLLER_PATH, return_value=mock_DayBetter_api):
        entry = MockConfigEntry(domain=DOMAIN, data={"host": "192.168.1.100"})
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert len(hass.states.async_all()) == 1

        light = hass.states.get("light.P076")
        assert light is not None

        assert light.state == "off"
        # Set RGB
        rgb_color = (100, 255, 50)
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {"entity_id": light.entity_id, ATTR_RGB_COLOR: rgb_color},
            blocking=True,
        )
        await hass.async_block_till_done()

        light = hass.states.get("light.P076")
        assert light is not None
        assert light.state == "on"
        assert light.attributes[ATTR_RGB_COLOR] == (100, 255, 50)
        assert light.attributes["color_mode"] == ColorMode.RGB

        assert light.attributes[ATTR_RGB_COLOR] == rgb_color
        mock_DayBetter_api.set_color.assert_awaited_with(
            device, rgb=rgb_color, temperature=None
        )

        # Set color temperature
        kelvin = 4400
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {"entity_id": light.entity_id, ATTR_COLOR_TEMP_KELVIN: kelvin},
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


# ----------------------------- Scene Tests -----------------------------
async def test_scene_on(hass: HomeAssistant, mock_DayBetter_api: AsyncMock) -> None:
    """Test turning on a scene."""
    device = create_mock_device(mock_DayBetter_api, capabilities=SCENE_CAPABILITIES)
    mock_DayBetter_api.devices = [device]

    mock_DayBetter_api.start = AsyncMock()
    mock_DayBetter_api.set_scene = AsyncMock()
    mock_DayBetter_api.turn_on_off = AsyncMock()

    with patch(CONTROLLER_PATH, return_value=mock_DayBetter_api):
        entry = MockConfigEntry(domain=DOMAIN, data={"host": "192.168.1.100"})
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        light = hass.states.get("light.P076")
        assert light is not None

        assert light.state == "off"

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


async def test_scene_restore_rgb(
    hass: HomeAssistant, mock_DayBetter_api: AsyncMock
) -> None:
    """Test restoring previous RGB color after scene ends."""
    device = create_mock_device(mock_DayBetter_api, capabilities=SCENE_CAPABILITIES)
    mock_DayBetter_api.devices = [device]

    mock_DayBetter_api.start = AsyncMock()
    mock_DayBetter_api.set_scene = AsyncMock()
    mock_DayBetter_api.turn_on_off = AsyncMock()
    mock_DayBetter_api.set_color = AsyncMock()

    with patch(CONTROLLER_PATH, return_value=mock_DayBetter_api):
        entry = MockConfigEntry(domain=DOMAIN, data={"host": "192.168.1.100"})
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert len(hass.states.async_all()) == 1

        initial_color = (12, 34, 56)
        light = hass.states.get("light.P076")
        assert light is not None
        assert light.state == "off"

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
    """Test restoring previous color temperature after scene ends."""
    device = create_mock_device(mock_DayBetter_api, capabilities=SCENE_CAPABILITIES)
    mock_DayBetter_api.devices = [device]

    mock_DayBetter_api.start = AsyncMock()
    mock_DayBetter_api.set_scene = AsyncMock()
    mock_DayBetter_api.turn_on_off = AsyncMock()
    mock_DayBetter_api.set_color = AsyncMock()

    with patch(CONTROLLER_PATH, return_value=mock_DayBetter_api):
        entry = MockConfigEntry(domain=DOMAIN, data={"host": "192.168.1.100"})
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


async def test_scene_none(hass: HomeAssistant, mock_DayBetter_api: AsyncMock) -> None:
    """Test activating 'none' scene does not call set_scene."""
    device = create_mock_device(mock_DayBetter_api, capabilities=SCENE_CAPABILITIES)
    mock_DayBetter_api.devices = [device]

    mock_DayBetter_api.start = AsyncMock()
    mock_DayBetter_api.set_scene = AsyncMock()
    mock_DayBetter_api.turn_on_off = AsyncMock()
    mock_DayBetter_api.set_color = AsyncMock()

    with patch(CONTROLLER_PATH, return_value=mock_DayBetter_api):
        entry = MockConfigEntry(domain=DOMAIN, data={"host": "192.168.1.100"})
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        light = hass.states.get("light.P076")
        assert light is not None
        # Activate 'none' scene
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {"entity_id": light.entity_id, ATTR_EFFECT: "none"},
            blocking=True,
        )
        await hass.async_block_till_done()
        assert light.attributes[ATTR_EFFECT] is None
        mock_DayBetter_api.set_scene.assert_not_called()
