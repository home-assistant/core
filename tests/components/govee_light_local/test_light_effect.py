"""Test Govee light local."""

from unittest.mock import MagicMock

from govee_local_api import GoveeDevice

from homeassistant.components.govee_light_local.const import DOMAIN
from homeassistant.core import HomeAssistant

from .conftest import SCENE_CAPABILITIES

from tests.common import MockConfigEntry


async def test_scene_on(hass: HomeAssistant, mock_govee_api: MagicMock) -> None:
    """Test adding a known device."""

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
        "light",
        "turn_on",
        {"entity_id": light.entity_id, "effect": "sunrise"},
        blocking=True,
    )
    await hass.async_block_till_done()

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "on"
    assert light.attributes["effect"] == "sunrise"
    mock_govee_api.turn_on_off.assert_awaited_with(mock_govee_api.devices[0], True)


async def test_scene_restore_rgb(
    hass: HomeAssistant, mock_govee_api: MagicMock
) -> None:
    """Test adding a known device."""

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
        "light",
        "turn_on",
        {"entity_id": light.entity_id, "rgb_color": initial_color},
        blocking=True,
    )
    await hass.async_block_till_done()
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": light.entity_id, "brightness": 255},
        blocking=True,
    )
    await hass.async_block_till_done()

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "on"
    assert light.attributes["rgb_color"] == initial_color
    assert light.attributes["brightness"] == 255
    mock_govee_api.turn_on_off.assert_awaited_with(mock_govee_api.devices[0], True)

    # Activate scene
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": light.entity_id, "effect": "sunrise"},
        blocking=True,
    )
    await hass.async_block_till_done()

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "on"
    assert light.attributes["effect"] == "sunrise"
    mock_govee_api.turn_on_off.assert_awaited_with(mock_govee_api.devices[0], True)

    # Deactivate scene
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": light.entity_id, "effect": "none"},
        blocking=True,
    )
    await hass.async_block_till_done()

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "on"
    assert light.attributes["effect"] is None
    assert light.attributes["rgb_color"] == initial_color
    assert light.attributes["brightness"] == 255


async def test_scene_restore_temperature(
    hass: HomeAssistant, mock_govee_api: MagicMock
) -> None:
    """Test adding a known device."""

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
        "light",
        "turn_on",
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
        "light",
        "turn_on",
        {"entity_id": light.entity_id, "effect": "sunrise"},
        blocking=True,
    )
    await hass.async_block_till_done()

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "on"
    assert light.attributes["effect"] == "sunrise"
    mock_govee_api.set_scene.assert_awaited_with(mock_govee_api.devices[0], "sunrise")

    # Deactivate scene
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": light.entity_id, "effect": "none"},
        blocking=True,
    )
    await hass.async_block_till_done()

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "on"
    assert light.attributes["effect"] is None
    assert light.attributes["color_temp_kelvin"] == initial_color


async def test_scene_none(hass: HomeAssistant, mock_govee_api: MagicMock) -> None:
    """Test adding a known device."""

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
        "light",
        "turn_on",
        {"entity_id": light.entity_id, "rgb_color": initial_color},
        blocking=True,
    )
    await hass.async_block_till_done()
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": light.entity_id, "brightness": 255},
        blocking=True,
    )
    await hass.async_block_till_done()

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "on"
    assert light.attributes["rgb_color"] == initial_color
    assert light.attributes["brightness"] == 255
    mock_govee_api.turn_on_off.assert_awaited_with(mock_govee_api.devices[0], True)

    # Activate scene
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": light.entity_id, "effect": "none"},
        blocking=True,
    )
    await hass.async_block_till_done()

    light = hass.states.get("light.H615A")
    assert light is not None
    assert light.state == "on"
    assert light.attributes["effect"] is None
    mock_govee_api.set_scene.assert_not_called()
