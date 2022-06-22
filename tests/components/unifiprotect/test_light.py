"""Test the UniFi Protect light platform."""
# pylint: disable=protected-access
from __future__ import annotations

from copy import copy
from unittest.mock import AsyncMock, Mock

import pytest
from pyunifiprotect.data import Light

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

from .conftest import (
    MockEntityFixture,
    add_device_ref,
    adopt_devices,
    assert_entity_counts,
    regenerate_device_ids,
    remove_entities,
)


@pytest.fixture(name="light")
async def light_fixture(
    hass: HomeAssistant, mock_entry: MockEntityFixture, mock_light: Light
):
    """Fixture for a single light for testing the light platform."""

    # disable pydantic validation so mocking can happen
    Light.__config__.validate_assignment = False

    light_obj = mock_light.copy()
    light_obj._api = mock_entry.api
    light_obj.name = "Test Light"
    light_obj.is_light_on = False
    regenerate_device_ids(light_obj)

    no_light_obj = mock_light.copy()
    no_light_obj._api = mock_entry.api
    no_light_obj.name = "Unadopted Light"
    no_light_obj.is_adopted = False
    regenerate_device_ids(no_light_obj)

    mock_entry.api.bootstrap.lights = {
        light_obj.id: light_obj,
        no_light_obj.id: no_light_obj,
    }
    add_device_ref(mock_entry.api.bootstrap, light_obj)
    add_device_ref(mock_entry.api.bootstrap, no_light_obj)

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    assert_entity_counts(hass, Platform.LIGHT, 1, 1)
    await remove_entities(hass, [light_obj, no_light_obj])
    assert_entity_counts(hass, Platform.LIGHT, 0, 0)
    await adopt_devices(hass, mock_entry.api, [light_obj, no_light_obj])
    assert_entity_counts(hass, Platform.LIGHT, 1, 1)

    yield (light_obj, "light.test_light")

    Light.__config__.validate_assignment = True


async def test_light_setup(
    hass: HomeAssistant,
    light: tuple[Light, str],
):
    """Test light entity setup."""

    unique_id = light[0].mac
    entity_id = light[1]

    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == unique_id

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION


async def test_light_update(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    light: tuple[Light, str],
):
    """Test light entity update."""

    new_bootstrap = copy(mock_entry.api.bootstrap)
    new_light = light[0].copy()
    new_light.is_light_on = True
    new_light.light_device_settings.led_level = 3

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_light

    new_bootstrap.lights = {new_light.id: new_light}
    mock_entry.api.bootstrap = new_bootstrap
    mock_entry.api.ws_subscription(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(light[1])
    assert state
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 128


async def test_light_turn_on(
    hass: HomeAssistant,
    light: tuple[Light, str],
):
    """Test light entity turn off."""

    entity_id = light[1]
    light[0].__fields__["set_light"] = Mock()
    light[0].set_light = AsyncMock()

    await hass.services.async_call(
        "light",
        "turn_on",
        {ATTR_ENTITY_ID: entity_id, ATTR_BRIGHTNESS: 128},
        blocking=True,
    )

    light[0].set_light.assert_called_once_with(True, 3)


async def test_light_turn_off(
    hass: HomeAssistant,
    light: tuple[Light, str],
):
    """Test light entity turn on."""

    entity_id = light[1]
    light[0].__fields__["set_light"] = Mock()
    light[0].set_light = AsyncMock()

    await hass.services.async_call(
        "light",
        "turn_off",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    light[0].set_light.assert_called_once_with(False)
