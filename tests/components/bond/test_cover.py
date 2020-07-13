"""Tests for the Bond cover device."""
from datetime import timedelta
import logging

from bond import DeviceTypes

from homeassistant import core
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_STOP_COVER,
)
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.util import utcnow

from .common import setup_platform

from tests.async_mock import patch
from tests.common import async_fire_time_changed

_LOGGER = logging.getLogger(__name__)


def shades(name: str):
    """Create motorized shades with given name."""
    return {"name": name, "type": DeviceTypes.MOTORIZED_SHADES}


async def test_entity_registry(hass: core.HomeAssistant):
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, COVER_DOMAIN, shades("name-1"))

    registry: EntityRegistry = await hass.helpers.entity_registry.async_get_registry()
    assert [key for key in registry.entities.keys()] == ["cover.name_1"]


async def test_open_cover(hass: core.HomeAssistant):
    """Tests that open cover command delegates to API."""
    await setup_platform(hass, COVER_DOMAIN, shades("name-1"))

    with patch("homeassistant.components.bond.Bond.open") as mock_open:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: "cover.name_1"},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_open.assert_called_once()


async def test_close_cover(hass: core.HomeAssistant):
    """Tests that close cover command delegates to API."""
    await setup_platform(hass, COVER_DOMAIN, shades("name-1"))

    with patch("homeassistant.components.bond.Bond.close") as mock_close:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: "cover.name_1"},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_close.assert_called_once()


async def test_stop_cover(hass: core.HomeAssistant):
    """Tests that stop cover command delegates to API."""
    await setup_platform(hass, COVER_DOMAIN, shades("name-1"))

    with patch("homeassistant.components.bond.Bond.hold") as mock_hold:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_STOP_COVER,
            {ATTR_ENTITY_ID: "cover.name_1"},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_hold.assert_called_once()


async def test_update_reports_open_cover(hass: core.HomeAssistant):
    """Tests that update command sets correct state when Bond API reports cover is open."""
    await setup_platform(hass, COVER_DOMAIN, shades("name-1"))

    with patch(
        "homeassistant.components.bond.Bond.getDeviceState", return_value={"open": 1}
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
        await hass.async_block_till_done()

    assert hass.states.get("cover.name_1").state == "open"


async def test_update_reports_closed_cover(hass: core.HomeAssistant):
    """Tests that update command sets correct state when Bond API reports cover is closed."""
    await setup_platform(hass, COVER_DOMAIN, shades("name-1"))

    with patch(
        "homeassistant.components.bond.Bond.getDeviceState", return_value={"open": 0}
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
        await hass.async_block_till_done()

    assert hass.states.get("cover.name_1").state == "closed"
