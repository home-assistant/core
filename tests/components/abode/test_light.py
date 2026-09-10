"""Tests for the Abode light device."""

from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_platform

from tests.common import snapshot_platform

DEVICE_ID = "light.living_room_lamp"


async def test_all_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all entities."""
    config_entry = await setup_platform(hass, LIGHT_DOMAIN)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_switch_off(hass: HomeAssistant) -> None:
    """Test the light can be turned off."""
    await setup_platform(hass, LIGHT_DOMAIN)

    with patch("jaraco.abode.devices.light.Light.switch_off") as mock_switch_off:
        await hass.services.async_call(
            LIGHT_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: DEVICE_ID}, blocking=True
        )
        await hass.async_block_till_done()
        mock_switch_off.assert_called_once()


async def test_switch_on(hass: HomeAssistant) -> None:
    """Test the light can be turned on."""
    await setup_platform(hass, LIGHT_DOMAIN)

    with patch("jaraco.abode.devices.light.Light.switch_on") as mock_switch_on:
        await hass.services.async_call(
            LIGHT_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: DEVICE_ID}, blocking=True
        )
        await hass.async_block_till_done()
        mock_switch_on.assert_called_once()


async def test_set_brightness(hass: HomeAssistant) -> None:
    """Test the brightness can be set."""
    await setup_platform(hass, LIGHT_DOMAIN)

    with patch("jaraco.abode.devices.light.Light.set_level") as mock_set_level:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: DEVICE_ID, "brightness": 100},
            blocking=True,
        )
        await hass.async_block_till_done()
        # Brightness is converted in abode.light.AbodeLight.turn_on
        mock_set_level.assert_called_once_with(39)


async def test_set_color(hass: HomeAssistant) -> None:
    """Test the color can be set."""
    await setup_platform(hass, LIGHT_DOMAIN)

    with patch("jaraco.abode.devices.light.Light.set_color") as mock_set_color:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: DEVICE_ID, "hs_color": [240, 100]},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_color.assert_called_once_with((240.0, 100.0))


async def test_set_color_temp(hass: HomeAssistant) -> None:
    """Test the color temp can be set."""
    await setup_platform(hass, LIGHT_DOMAIN)

    with patch(
        "jaraco.abode.devices.light.Light.set_color_temp"
    ) as mock_set_color_temp:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: DEVICE_ID, "color_temp_kelvin": 3236},
            blocking=True,
        )
        await hass.async_block_till_done()
        # Color temp is converted in abode.light.AbodeLight.turn_on
        mock_set_color_temp.assert_called_once_with(3236)
