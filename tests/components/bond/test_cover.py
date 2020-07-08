"""Tests for the Bond cover device."""
import logging

from bond import BOND_DEVICE_TYPE_MOTORIZED_SHADES

from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_STOP_COVER,
)
from homeassistant.helpers.entity_registry import EntityRegistry

from .common import setup_platform

from tests.async_mock import patch

_LOGGER = logging.getLogger(__name__)

TEST_DEVICE_IDS = ["device-1"]
TEST_DEVICE = {"name": "name-1", "type": BOND_DEVICE_TYPE_MOTORIZED_SHADES}


async def test_entity_registry(hass):
    """Tests that the devices are registered in the entity registry."""

    with patch(
        "homeassistant.components.bond.Bond.getDeviceIds", return_value=TEST_DEVICE_IDS
    ), patch("homeassistant.components.bond.Bond.getDevice", return_value=TEST_DEVICE):
        await setup_platform(hass, COVER_DOMAIN)

    registry: EntityRegistry = await hass.helpers.entity_registry.async_get_registry()
    assert [key for key in registry.entities.keys()] == ["cover.name_1"]


async def test_open_cover(hass):
    """Tests that open cover command delegates to API."""

    with patch(
        "homeassistant.components.bond.Bond.getDeviceIds", return_value=TEST_DEVICE_IDS
    ), patch("homeassistant.components.bond.Bond.getDevice", return_value=TEST_DEVICE):
        await setup_platform(hass, COVER_DOMAIN)

    with patch("homeassistant.components.bond.Bond.open") as mock_open:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: "cover.name_1"},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_open.assert_called_once()


async def test_close_cover(hass):
    """Tests that close cover command delegates to API."""

    with patch(
        "homeassistant.components.bond.Bond.getDeviceIds", return_value=TEST_DEVICE_IDS
    ), patch("homeassistant.components.bond.Bond.getDevice", return_value=TEST_DEVICE):
        await setup_platform(hass, COVER_DOMAIN)

    with patch("homeassistant.components.bond.Bond.close") as mock_close:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: "cover.name_1"},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_close.assert_called_once()


async def test_stop_cover(hass):
    """Tests that stop cover command delegates to API."""

    with patch(
        "homeassistant.components.bond.Bond.getDeviceIds", return_value=TEST_DEVICE_IDS
    ), patch("homeassistant.components.bond.Bond.getDevice", return_value=TEST_DEVICE):
        await setup_platform(hass, COVER_DOMAIN)

    with patch("homeassistant.components.bond.Bond.hold") as mock_hold:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_STOP_COVER,
            {ATTR_ENTITY_ID: "cover.name_1"},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_hold.assert_called_once()
