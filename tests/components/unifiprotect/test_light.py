"""Test the UniFi Protect light platform."""
# pylint: disable=protected-access
from __future__ import annotations

from unittest.mock import AsyncMock, Mock

from pyunifiprotect.data import Light
from pyunifiprotect.data.types import LEDLevel

from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.components.unifiprotect.const import DEFAULT_ATTRIBUTION
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .utils import (
    MockUFPFixture,
    adopt_devices,
    assert_entity_counts,
    init_entry,
    remove_entities,
)


async def test_light_remove(hass: HomeAssistant, ufp: MockUFPFixture, light: Light):
    """Test removing and re-adding a light device."""

    await init_entry(hass, ufp, [light])
    assert_entity_counts(hass, Platform.LIGHT, 1, 1)
    await remove_entities(hass, ufp, [light])
    assert_entity_counts(hass, Platform.LIGHT, 0, 0)
    await adopt_devices(hass, ufp, [light])
    assert_entity_counts(hass, Platform.LIGHT, 1, 1)


async def test_light_setup(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light, unadopted_light: Light
):
    """Test light entity setup."""

    await init_entry(hass, ufp, [light, unadopted_light])
    assert_entity_counts(hass, Platform.LIGHT, 1, 1)

    unique_id = light.mac
    entity_id = "light.test_light"

    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == unique_id

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_light_update(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light, unadopted_light: Light
):
    """Test light entity update."""

    await init_entry(hass, ufp, [light, unadopted_light])
    assert_entity_counts(hass, Platform.LIGHT, 1, 1)

    new_light = light.copy()
    new_light.is_light_on = True
    new_light.light_device_settings.led_level = LEDLevel(3)

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_light

    ufp.api.bootstrap.lights = {new_light.id: new_light}
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get("light.test_light")
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 128


async def test_light_turn_on(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light, unadopted_light: Light
):
    """Test light entity turn off."""

    await init_entry(hass, ufp, [light, unadopted_light])
    assert_entity_counts(hass, Platform.LIGHT, 1, 1)

    entity_id = "light.test_light"
    light.__fields__["set_light"] = Mock(final=False)
    light.set_light = AsyncMock()

    await hass.services.async_call(
        "light",
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 128},
        blocking=True,
    )

    light.set_light.assert_called_once_with(True, 3)


async def test_light_turn_off(
    hass: HomeAssistant, ufp: MockUFPFixture, light: Light, unadopted_light: Light
):
    """Test light entity turn on."""

    await init_entry(hass, ufp, [light, unadopted_light])
    assert_entity_counts(hass, Platform.LIGHT, 1, 1)

    entity_id = "light.test_light"
    light.__fields__["set_light"] = Mock(final=False)
    light.set_light = AsyncMock()

    await hass.services.async_call(
        "light",
        "turn_off",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    light.set_light.assert_called_once_with(False)
