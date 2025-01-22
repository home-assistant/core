"""Tests for the integration of a twinly device."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion
from ttls.client import TwinklyError

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    LightEntityFeature,
)
from homeassistant.components.twinkly import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration
from .const import TEST_MAC

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.mark.usefixtures("mock_twinkly_client")
async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the created entities."""
    with patch("homeassistant.components.twinkly.PLATFORMS", [Platform.LIGHT]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_turn_on_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_twinkly_client: AsyncMock,
) -> None:
    """Test support of the light.turn_on service."""
    mock_twinkly_client.is_on.return_value = False

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("light.tree_1").state == STATE_OFF

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        service_data={ATTR_ENTITY_ID: "light.tree_1"},
        blocking=True,
    )

    mock_twinkly_client.turn_on.assert_called_once_with()


async def test_turn_on_with_brightness(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_twinkly_client: AsyncMock,
) -> None:
    """Test support of the light.turn_on service with a brightness parameter."""
    mock_twinkly_client.is_on.return_value = False

    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        service_data={ATTR_ENTITY_ID: "light.tree_1", ATTR_BRIGHTNESS: 255},
        blocking=True,
    )

    mock_twinkly_client.set_brightness.assert_called_once_with(100)
    mock_twinkly_client.turn_on.assert_called_once_with()


async def test_brightness_to_zero(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_twinkly_client: AsyncMock,
) -> None:
    """Test support of the light.turn_on service with a brightness parameter."""
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        service_data={ATTR_ENTITY_ID: "light.tree_1", ATTR_BRIGHTNESS: 1},
        blocking=True,
    )

    mock_twinkly_client.set_brightness.assert_not_called()
    mock_twinkly_client.turn_off.assert_called_once_with()


async def test_turn_on_with_color_rgbw(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_twinkly_client: AsyncMock,
) -> None:
    """Test support of the light.turn_on service with a rgbw parameter."""
    mock_twinkly_client.is_on.return_value = False
    mock_twinkly_client.get_details.return_value["led_profile"] = "RGBW"

    await setup_integration(hass, mock_config_entry)
    assert (
        LightEntityFeature.EFFECT
        & hass.states.get("light.tree_1").attributes[ATTR_SUPPORTED_FEATURES]
    )

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        service_data={
            ATTR_ENTITY_ID: "light.tree_1",
            ATTR_RGBW_COLOR: (128, 64, 32, 0),
        },
        blocking=True,
    )

    mock_twinkly_client.interview.assert_called_once_with()
    mock_twinkly_client.set_static_colour.assert_called_once_with((128, 64, 32))
    mock_twinkly_client.set_mode.assert_called_once_with("color")
    assert mock_twinkly_client.default_mode == "color"


async def test_turn_on_with_color_rgb(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_twinkly_client: AsyncMock,
) -> None:
    """Test support of the light.turn_on service with a rgb parameter."""
    mock_twinkly_client.is_on.return_value = False
    mock_twinkly_client.get_details.return_value["led_profile"] = "RGB"

    await setup_integration(hass, mock_config_entry)
    assert (
        LightEntityFeature.EFFECT
        & hass.states.get("light.tree_1").attributes[ATTR_SUPPORTED_FEATURES]
    )

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        service_data={ATTR_ENTITY_ID: "light.tree_1", ATTR_RGB_COLOR: (128, 64, 32)},
        blocking=True,
    )

    mock_twinkly_client.interview.assert_called_once_with()
    mock_twinkly_client.set_static_colour.assert_called_once_with((128, 64, 32))
    mock_twinkly_client.set_mode.assert_called_once_with("color")
    assert mock_twinkly_client.default_mode == "color"


async def test_turn_on_with_effect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_twinkly_client: AsyncMock,
) -> None:
    """Test support of the light.turn_on service with effects."""
    mock_twinkly_client.is_on.return_value = False
    mock_twinkly_client.get_details.return_value["led_profile"] = "RGB"

    await setup_integration(hass, mock_config_entry)
    assert (
        LightEntityFeature.EFFECT
        & hass.states.get("light.tree_1").attributes[ATTR_SUPPORTED_FEATURES]
    )

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        service_data={ATTR_ENTITY_ID: "light.tree_1", ATTR_EFFECT: "2 Rainbow"},
        blocking=True,
    )

    mock_twinkly_client.interview.assert_called_once_with()
    mock_twinkly_client.set_current_movie.assert_called_once_with(2)
    mock_twinkly_client.set_mode.assert_called_once_with("movie")
    assert mock_twinkly_client.default_mode == "movie"


@pytest.mark.parametrize(
    ("data"),
    [
        {ATTR_RGBW_COLOR: (128, 64, 32, 0)},
        {ATTR_RGB_COLOR: (128, 64, 32)},
    ],
)
async def test_turn_on_with_missing_effect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_twinkly_client: AsyncMock,
    data: dict[str, Any],
) -> None:
    """Test support of the light.turn_on service with rgbw color and missing effect support."""
    mock_twinkly_client.is_on.return_value = False
    mock_twinkly_client.get_firmware_version.return_value["version"] = "2.7.0"

    await setup_integration(hass, mock_config_entry)
    assert (
        LightEntityFeature.EFFECT
        ^ hass.states.get("light.tree_1").attributes[ATTR_SUPPORTED_FEATURES]
    )

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        service_data={ATTR_ENTITY_ID: "light.tree_1"} | data,
        blocking=True,
    )

    mock_twinkly_client.interview.assert_called_once_with()
    mock_twinkly_client.set_cycle_colours.assert_called_once_with((128, 64, 32))
    mock_twinkly_client.set_mode.assert_called_once_with("movie")
    assert mock_twinkly_client.default_mode == "movie"
    mock_twinkly_client.set_current_movie.assert_not_called()


async def test_turn_on_with_color_rgbw_and_missing_effect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_twinkly_client: AsyncMock,
) -> None:
    """Test support of the light.turn_on service with missing effect support."""
    mock_twinkly_client.is_on.return_value = False
    mock_twinkly_client.get_firmware_version.return_value["version"] = "2.7.0"

    await setup_integration(hass, mock_config_entry)
    assert (
        LightEntityFeature.EFFECT
        ^ hass.states.get("light.tree_1").attributes[ATTR_SUPPORTED_FEATURES]
    )

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        service_data={ATTR_ENTITY_ID: "light.tree_1", ATTR_EFFECT: "2 Rainbow"},
        blocking=True,
    )

    mock_twinkly_client.set_current_movie.assert_not_called()


async def test_turn_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_twinkly_client: AsyncMock,
) -> None:
    """Test support of the light.turn_off service."""

    await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        service_data={ATTR_ENTITY_ID: "light.tree_1"},
        blocking=True,
    )
    mock_twinkly_client.turn_off.assert_called_once_with()


async def test_no_current_movie(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_twinkly_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test handling of missing current movie data."""

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("light.tree_1").attributes[ATTR_EFFECT] == "1 Rainbow"

    mock_twinkly_client.get_current_movie.side_effect = TwinklyError

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("light.tree_1").state != STATE_UNAVAILABLE
    assert hass.states.get("light.tree_1").attributes[ATTR_EFFECT] is None


async def test_update_name(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_twinkly_client: AsyncMock,
) -> None:
    """Validate device's name update behavior.

    Validate that if device name is changed from the Twinkly app,
    then the name of the entity is updated and it's also persisted,
    so it can be restored when starting HA while Twinkly is offline.
    """

    await setup_integration(hass, mock_config_entry)

    dev_entry = device_registry.async_get_device({(DOMAIN, TEST_MAC)})

    assert dev_entry.name == "Tree 1"

    mock_twinkly_client.get_details.return_value["device_name"] = "new_device_name"

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    dev_entry = device_registry.async_get_device({(DOMAIN, TEST_MAC)})

    assert dev_entry.name == "new_device_name"
