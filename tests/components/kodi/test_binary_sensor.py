"""The tests for Kodi binary sensor platform."""
import logging
from unittest.mock import patch

import pytest

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity

from . import init_integration

_LOGGER = logging.getLogger(__name__)


@pytest.mark.parametrize(
    "element, name",
    [("screensaver", "Screensaver"), ("energy_saving", "Energy saving")],
)
async def test_binary_sensor_initial_states(hass: HomeAssistant, element, name):
    """Test for binary sensor values."""
    entry = await init_integration(hass)

    state = hass.states.get(f"binary_sensor.{entry.data['name']}_{element}")
    assert state.state == STATE_OFF
    assert state.attributes["friendly_name"] == f"{entry.data['name']} {name}"


@pytest.mark.parametrize("element", ["screensaver", "energy_saving"])
async def test_binary_sensor_statechange(hass: HomeAssistant, element):
    """Test the event."""
    entry = await init_integration(hass)

    state = hass.states.get(f"binary_sensor.{entry.data['name']}_{element}")
    assert state.state == STATE_OFF

    hass.states.async_set(f"binary_sensor.{entry.data['name']}_{element}", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get(f"binary_sensor.{entry.data['name']}_{element}")
    assert state.state == STATE_ON


@pytest.mark.parametrize(
    "element, boolean",
    [
        ("screensaver", "System.ScreenSaverActive"),
        ("energy_saving", "System.DPMSActive"),
    ],
)
async def test_binary_sensor_update(hass: HomeAssistant, element, boolean):
    """Test the async_update method."""
    entry = await init_integration(hass)
    entity_id = f"binary_sensor.{entry.data['name']}_{element}"

    with patch(
        "homeassistant.components.kodi.KodiConnectionManager.connected",
        return_value=True,
    ), patch("pykodi.Kodi.call_method", return_value={boolean: True}):
        await async_update_entity(hass, entity_id)
        await hass.async_block_till_done()

    assert (
        hass.states.get(f"binary_sensor.{entry.data['name']}_{element}").state
        == STATE_ON
    )

    with patch(
        "homeassistant.components.kodi.KodiConnectionManager.connected",
        return_value=True,
    ), patch("pykodi.Kodi.call_method", return_value={boolean: False}):
        await async_update_entity(hass, entity_id)
        await hass.async_block_till_done()

    assert (
        hass.states.get(f"binary_sensor.{entry.data['name']}_{element}").state
        == STATE_OFF
    )
