"""Tests for home_connect light entities."""

from collections.abc import Awaitable, Callable
from unittest.mock import patch

from homeconnect import HomeConnectAPI
from homeconnect.api import HomeConnectError

from homeassistant.components.home_connect.const import (
    ATTR_VALUE,
    BSH_AMBIENT_LIGHT_BRIGHTNESS,
    BSH_AMBIENT_LIGHT_CUSTOM_COLOR,
    BSH_AMBIENT_LIGHT_ENABLED,
    COOKING_LIGHTING,
    COOKING_LIGHTING_BRIGHTNESS,
    DOMAIN,
    SIGNAL_UPDATE_ENTITIES,
)
from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_HS_COLOR
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import dispatcher_send

from .conftest import get_appliances

from tests.common import MockConfigEntry

TEST_HC_APP = "Hood"


async def test_light(
    bypass_throttle,
    platforms,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    setup_credentials: None,
    problematic_appliance,
) -> None:
    """Test light entities."""
    platforms = [Platform.LIGHT]
    assert config_entry.state == ConfigEntryState.NOT_LOADED
    with patch.object(
        HomeConnectAPI,
        "get_appliances",
        side_effect=lambda: get_appliances(hass.data[DOMAIN][config_entry.entry_id]),
    ):
        assert await integration_setup()
    assert config_entry.state == ConfigEntryState.LOADED
    await hass.config_entries.async_forward_entry_setups(config_entry, platforms)

    assert hass.states.is_state("light.hood_light", "on")

    (hc_app,) = (
        x["device"].appliance
        for x in hass.data[DOMAIN][config_entry.entry_id].devices
        if x["device"].appliance.type == TEST_HC_APP
    )

    hc_app.status.update({COOKING_LIGHTING: {ATTR_VALUE: None}})

    dispatcher_send(hass, SIGNAL_UPDATE_ENTITIES, hc_app.haId)
    await hass.async_block_till_done()

    assert hass.states.is_state("light.hood_light", "unknown")

    hc_app.status.update({COOKING_LIGHTING_BRIGHTNESS: {ATTR_VALUE: 55}})
    hc_app.status.update({COOKING_LIGHTING: {ATTR_VALUE: False}})
    hc_app.status.update({BSH_AMBIENT_LIGHT_BRIGHTNESS: {ATTR_VALUE: 55}})
    hc_app.status.update({BSH_AMBIENT_LIGHT_ENABLED: {ATTR_VALUE: False}})

    dispatcher_send(hass, SIGNAL_UPDATE_ENTITIES, hc_app.haId)
    await hass.async_block_till_done()

    assert hass.states.is_state("light.hood_light", "off")
    assert hass.states.is_state("light.hood_ambientlight", "off")

    await hass.services.async_call(
        "light", SERVICE_TURN_ON, {ATTR_ENTITY_ID: "light.hood_light"}, blocking=True
    )
    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.hood_light", ATTR_BRIGHTNESS: 77},
        blocking=True,
    )
    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.hood_ambientlight", ATTR_BRIGHTNESS: 10},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.is_state("light.hood_light", "on")
    assert hass.states.is_state("light.hood_ambientlight", "on")

    await hass.services.async_call(
        "light", SERVICE_TURN_OFF, {ATTR_ENTITY_ID: "light.hood_light"}, blocking=True
    )
    await hass.services.async_call(
        "light",
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.hood_ambientlight"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.is_state("light.hood_light", "off")
    assert hass.states.is_state("light.hood_ambientlight", "off")

    # Edge cases: ambient light with color loss | brightness set to None

    hc_app.status.pop(BSH_AMBIENT_LIGHT_CUSTOM_COLOR)
    hc_app.status.update({COOKING_LIGHTING_BRIGHTNESS: None})

    dispatcher_send(hass, SIGNAL_UPDATE_ENTITIES, hc_app.haId)
    await hass.async_block_till_done()

    # Test exceptions

    hc_app = problematic_appliance

    hc_app.status.update({BSH_AMBIENT_LIGHT_CUSTOM_COLOR: {ATTR_VALUE: "#4a88f8"}})
    hc_app.status.update({COOKING_LIGHTING_BRIGHTNESS: {ATTR_VALUE: 100}})

    hass.data[DOMAIN][config_entry.entry_id].devices[9]["device"].appliance = hc_app

    await hass.services.async_call(
        "light",
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.hood_light"},
        blocking=True,
    )
    await hass.services.async_call(
        "light",
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.hood_ambientlight"},
        blocking=True,
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.hood_light"},
        blocking=True,
    )
    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.hood_light", ATTR_BRIGHTNESS: 88},
        blocking=True,
    )
    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.hood_ambientlight"},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hc_app.set_setting.call_count == 5
    hc_app.set_setting.reset_mock()

    hc_app.set_setting.side_effect = [
        None,
        HomeConnectError,
        None,
        None,
        None,
        HomeConnectError,
    ]

    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.hood_ambientlight", ATTR_BRIGHTNESS: 50},
        blocking=True,
    )
    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.hood_ambientlight", ATTR_HS_COLOR: (128.00, 99.00)},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hc_app.set_setting.call_count == 6
