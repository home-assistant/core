"""Tests for the integration of a twinly device."""
from __future__ import annotations

from unittest.mock import patch

from homeassistant.components.light import ATTR_BRIGHTNESS, LightEntityFeature
from homeassistant.components.twinkly.const import (
    CONF_HOST,
    CONF_ID,
    CONF_NAME,
    DOMAIN as TWINKLY_DOMAIN,
)
from homeassistant.const import CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.entity_registry import RegistryEntry

from . import TEST_MODEL, TEST_NAME_ORIGINAL, ClientMock

from tests.common import MockConfigEntry


async def test_initial_state(hass: HomeAssistant) -> None:
    """Validate that entity and device states are updated on startup."""
    entity, device, _, _ = await _create_entries(hass)

    state = hass.states.get(entity.entity_id)

    # Basic state properties
    assert state.name == entity.unique_id
    assert state.state == "on"
    assert state.attributes[ATTR_BRIGHTNESS] == 26
    assert state.attributes["friendly_name"] == entity.unique_id
    assert state.attributes["icon"] == "mdi:string-lights"

    assert entity.original_name == entity.unique_id
    assert entity.original_icon == "mdi:string-lights"

    assert device.name == entity.unique_id
    assert device.model == TEST_MODEL
    assert device.manufacturer == "LEDWORKS"


async def test_turn_on_off(hass: HomeAssistant) -> None:
    """Test support of the light.turn_on service."""
    client = ClientMock()
    client.state = False
    client.brightness = {"mode": "enabled", "value": 20}
    entity, _, _, _ = await _create_entries(hass, client)

    assert hass.states.get(entity.entity_id).state == "off"

    await hass.services.async_call(
        "light", "turn_on", service_data={"entity_id": entity.entity_id}, blocking=True
    )

    state = hass.states.get(entity.entity_id)

    assert state.state == "on"
    assert state.attributes[ATTR_BRIGHTNESS] == 51


async def test_turn_on_with_brightness(hass: HomeAssistant) -> None:
    """Test support of the light.turn_on service with a brightness parameter."""
    client = ClientMock()
    client.state = False
    client.brightness = {"mode": "enabled", "value": 20}
    entity, _, _, _ = await _create_entries(hass, client)

    assert hass.states.get(entity.entity_id).state == "off"

    await hass.services.async_call(
        "light",
        "turn_on",
        service_data={"entity_id": entity.entity_id, "brightness": 255},
        blocking=True,
    )

    state = hass.states.get(entity.entity_id)

    assert state.state == "on"
    assert state.attributes[ATTR_BRIGHTNESS] == 255

    await hass.services.async_call(
        "light",
        "turn_on",
        service_data={"entity_id": entity.entity_id, "brightness": 1},
        blocking=True,
    )

    state = hass.states.get(entity.entity_id)

    assert state.state == "off"


async def test_turn_on_with_color_rgbw(hass: HomeAssistant) -> None:
    """Test support of the light.turn_on service with a rgbw parameter."""
    client = ClientMock()
    client.state = False
    client.device_info["led_profile"] = "RGBW"
    client.brightness = {"mode": "enabled", "value": 255}
    entity, _, _, _ = await _create_entries(hass, client)

    assert hass.states.get(entity.entity_id).state == "off"
    assert (
        LightEntityFeature.EFFECT
        & hass.states.get(entity.entity_id).attributes["supported_features"]
    )

    await hass.services.async_call(
        "light",
        "turn_on",
        service_data={"entity_id": entity.entity_id, "rgbw_color": (128, 64, 32, 0)},
        blocking=True,
    )

    state = hass.states.get(entity.entity_id)

    assert state.state == "on"
    assert client.color == (128, 64, 32)
    assert client.default_mode == "color"
    assert client.mode == "color"


async def test_turn_on_with_color_rgb(hass: HomeAssistant) -> None:
    """Test support of the light.turn_on service with a rgb parameter."""
    client = ClientMock()
    client.state = False
    client.device_info["led_profile"] = "RGB"
    client.brightness = {"mode": "enabled", "value": 255}
    entity, _, _, _ = await _create_entries(hass, client)

    assert hass.states.get(entity.entity_id).state == "off"
    assert (
        LightEntityFeature.EFFECT
        & hass.states.get(entity.entity_id).attributes["supported_features"]
    )

    await hass.services.async_call(
        "light",
        "turn_on",
        service_data={"entity_id": entity.entity_id, "rgb_color": (128, 64, 32)},
        blocking=True,
    )

    state = hass.states.get(entity.entity_id)

    assert state.state == "on"
    assert client.color == (128, 64, 32)
    assert client.default_mode == "color"
    assert client.mode == "color"


async def test_turn_on_with_effect(hass: HomeAssistant) -> None:
    """Test support of the light.turn_on service with effects."""
    client = ClientMock()
    client.state = False
    client.device_info["led_profile"] = "RGB"
    client.brightness = {"mode": "enabled", "value": 255}
    entity, _, _, _ = await _create_entries(hass, client)

    assert hass.states.get(entity.entity_id).state == "off"
    assert not client.current_movie
    assert (
        LightEntityFeature.EFFECT
        & hass.states.get(entity.entity_id).attributes["supported_features"]
    )

    await hass.services.async_call(
        "light",
        "turn_on",
        service_data={"entity_id": entity.entity_id, "effect": "1 Rainbow"},
        blocking=True,
    )

    state = hass.states.get(entity.entity_id)

    assert state.state == "on"
    assert client.current_movie["id"] == 1
    assert client.default_mode == "movie"
    assert client.mode == "movie"


async def test_turn_on_with_color_rgbw_and_missing_effect(hass: HomeAssistant) -> None:
    """Test support of the light.turn_on service with rgbw color and missing effect support."""
    client = ClientMock()
    client.state = False
    client.device_info["led_profile"] = "RGBW"
    client.brightness = {"mode": "enabled", "value": 255}
    client.version = "2.7.0"
    entity, _, _, _ = await _create_entries(hass, client)

    assert hass.states.get(entity.entity_id).state == "off"
    assert (
        not LightEntityFeature.EFFECT
        & hass.states.get(entity.entity_id).attributes["supported_features"]
    )

    await hass.services.async_call(
        "light",
        "turn_on",
        service_data={"entity_id": entity.entity_id, "rgbw_color": (128, 64, 32, 0)},
        blocking=True,
    )

    state = hass.states.get(entity.entity_id)

    assert state.state == "on"
    assert client.color == (0, 128, 64, 32)
    assert client.mode == "movie"
    assert client.default_mode == "movie"


async def test_turn_on_with_color_rgb_and_missing_effect(hass: HomeAssistant) -> None:
    """Test support of the light.turn_on service with rgb color and missing effect support."""
    client = ClientMock()
    client.state = False
    client.device_info["led_profile"] = "RGB"
    client.brightness = {"mode": "enabled", "value": 255}
    client.version = "2.7.0"
    entity, _, _, _ = await _create_entries(hass, client)

    assert hass.states.get(entity.entity_id).state == "off"
    assert (
        not LightEntityFeature.EFFECT
        & hass.states.get(entity.entity_id).attributes["supported_features"]
    )

    await hass.services.async_call(
        "light",
        "turn_on",
        service_data={"entity_id": entity.entity_id, "rgb_color": (128, 64, 32)},
        blocking=True,
    )

    state = hass.states.get(entity.entity_id)

    assert state.state == "on"
    assert client.color == (128, 64, 32)
    assert client.mode == "movie"
    assert client.default_mode == "movie"


async def test_turn_on_with_effect_missing_effects(hass: HomeAssistant) -> None:
    """Test support of the light.turn_on service with effect set even if effects are not supported."""
    client = ClientMock()
    client.state = False
    client.device_info["led_profile"] = "RGB"
    client.brightness = {"mode": "enabled", "value": 255}
    client.version = "2.7.0"
    entity, _, _, _ = await _create_entries(hass, client)

    assert hass.states.get(entity.entity_id).state == "off"
    assert not client.current_movie
    assert (
        not LightEntityFeature.EFFECT
        & hass.states.get(entity.entity_id).attributes["supported_features"]
    )

    await hass.services.async_call(
        "light",
        "turn_on",
        service_data={"entity_id": entity.entity_id, "effect": "1 Rainbow"},
        blocking=True,
    )

    state = hass.states.get(entity.entity_id)

    assert state.state == "on"
    assert not client.current_movie
    assert client.default_mode == "movie"
    assert client.mode == "movie"


async def test_turn_off(hass: HomeAssistant) -> None:
    """Test support of the light.turn_off service."""
    entity, _, _, _ = await _create_entries(hass)

    assert hass.states.get(entity.entity_id).state == "on"

    await hass.services.async_call(
        "light", "turn_off", service_data={"entity_id": entity.entity_id}, blocking=True
    )

    state = hass.states.get(entity.entity_id)

    assert state.state == "off"


async def test_update_name(hass: HomeAssistant) -> None:
    """Validate device's name update behavior.

    Validate that if device name is changed from the Twinkly app,
    then the name of the entity is updated and it's also persisted,
    so it can be restored when starting HA while Twinkly is offline.
    """
    entity, _, client, config_entry = await _create_entries(hass)

    client.change_name("new_device_name")
    await hass.services.async_call(
        "light", "turn_off", service_data={"entity_id": entity.entity_id}, blocking=True
    )  # We call turn_off which will automatically cause an async_update

    state = hass.states.get(entity.entity_id)

    assert config_entry.data[CONF_NAME] == "new_device_name"
    assert state.attributes["friendly_name"] == "new_device_name"


async def test_unload(hass: HomeAssistant) -> None:
    """Validate that entities can be unloaded from the UI."""

    _, _, client, _ = await _create_entries(hass)
    entry_id = client.id

    assert await hass.config_entries.async_unload(entry_id)


async def _create_entries(
    hass: HomeAssistant, client=None
) -> tuple[RegistryEntry, DeviceEntry, ClientMock]:
    client = ClientMock() if client is None else client

    with patch("homeassistant.components.twinkly.Twinkly", return_value=client):
        config_entry = MockConfigEntry(
            domain=TWINKLY_DOMAIN,
            data={
                CONF_HOST: client,
                CONF_ID: client.id,
                CONF_NAME: TEST_NAME_ORIGINAL,
                CONF_MODEL: TEST_MODEL,
            },
            entry_id=client.id,
        )
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(client.id)
        await hass.async_block_till_done()

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    entity_id = entity_registry.async_get_entity_id("light", TWINKLY_DOMAIN, client.id)
    entity_entry = entity_registry.async_get(entity_id)
    device = device_registry.async_get_device(identifiers={(TWINKLY_DOMAIN, client.id)})

    assert entity_entry is not None
    assert device is not None

    return entity_entry, device, client, config_entry
