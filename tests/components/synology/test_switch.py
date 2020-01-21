"""Tests for the Synology Switch device initialization."""
import logging
from unittest.mock import MagicMock, Mock

from synology.surveillance_station import SurveillanceStation

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.synology import const
from homeassistant.setup import async_setup_component

_LOGGER = logging.getLogger(__name__)


async def init_valid_switch(hass, mock_surveillance_station):
    """Initialize a valid switch for Synology component."""
    hass.data[const.DOMAIN_DATA] = {
        const.DATA_SURVEILLANCE_CLIENT: mock_surveillance_station,
        const.DATA_NAME: "Test Synology",
    }

    assert await async_setup_component(
        hass, SWITCH_DOMAIN, {"switch": {"platform": const.DOMAIN}}
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids("switch")) == 1


async def test_component_not_initialized(hass):
    """Test that switch skips initialization if synology component is not initialized."""
    assert await async_setup_component(
        hass, SWITCH_DOMAIN, {"switch": {"platform": const.DOMAIN}}
    )
    await hass.async_block_till_done()

    assert not hass.states.async_entity_ids("switch")


async def test_switch_initialized(hass):
    """Test that switch is initialized if synology component data is present."""
    await init_valid_switch(hass, Mock(SurveillanceStation))


async def test_switch(hass):
    """Test that switch is initialized if synology component data is present."""
    mock_surveillance_station = MagicMock(spec=SurveillanceStation)

    mock_surveillance_station.is_switched_on = MagicMock(return_value=True)

    await init_valid_switch(hass, mock_surveillance_station)

    switch_id = hass.states.async_entity_ids("switch")[0]
    switch = hass.states.get(switch_id)

    assert switch.state == "on"

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": switch_id}, blocking=True
    )

    mock_surveillance_station.set_home_mode.assert_called_with(False)

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": switch_id}, blocking=True
    )

    mock_surveillance_station.set_home_mode.assert_called_with(True)
