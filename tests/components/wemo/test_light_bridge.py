"""Tests for the Wemo light entity via the bridge."""

import pytest
import pywemo

from homeassistant.components.homeassistant import (
    DOMAIN as HA_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.setup import async_setup_component

from tests.async_mock import PropertyMock, create_autospec


@pytest.fixture
def pywemo_model():
    """Pywemo Bridge models use the light platform (WemoLight class)."""
    return "Bridge"


@pytest.fixture(name="pywemo_bridge_light")
def pywemo_bridge_light_fixture(pywemo_device):
    """Fixture for Bridge.Light WeMoDevice instances."""
    light = create_autospec(pywemo.ouimeaux_device.bridge.Light)
    light.uniqueID = pywemo_device.serialnumber
    light.name = pywemo_device.name
    pywemo_device.Lights = {pywemo_device.serialnumber: light}
    return light


async def test_light_update_entity(
    hass, pywemo_registry, pywemo_bridge_light, wemo_entity
):
    """Verify that the light performs state updates."""
    await async_setup_component(hass, HA_DOMAIN, {})

    # On state.
    type(pywemo_bridge_light).state = PropertyMock(return_value={"onoff": 1})
    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: [wemo_entity.entity_id]},
        blocking=True,
    )
    assert hass.states.get(wemo_entity.entity_id).state == STATE_ON

    # Off state.
    type(pywemo_bridge_light).state = PropertyMock(return_value={"onoff": 0})
    await hass.services.async_call(
        HA_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: [wemo_entity.entity_id]},
        blocking=True,
    )
    assert hass.states.get(wemo_entity.entity_id).state == STATE_OFF
