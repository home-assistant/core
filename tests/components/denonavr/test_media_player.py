"""The tests for the denonavr media player platform."""
from unittest.mock import MagicMock

from homeassistant.components import media_player
from homeassistant.components.demo import media_player as demo
import homeassistant.components.denonavr as denonavr
from homeassistant.components.denonavr import ATTR_COMMAND, DOMAIN, SERVICE_GET_COMMAND
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.setup import async_setup_component


async def test_setup_demo_platform(hass):
    """Test setup."""
    mock = MagicMock()
    add_entities = mock.MagicMock()
    await demo.async_setup_platform(hass, {}, add_entities)
    assert add_entities.call_count == 1


async def test_get_command(hass):
    """Test generic command functionality."""

    await hass.async_add_executor_job(denonavr.setup, hass, {})

    assert await async_setup_component(
        hass,
        media_player.DOMAIN,
        {"media_player": {"platform": "manual", "name": "test"}},
    )

    entity_id = "media_player.test"
    command = "/goform/formiPhoneAppDirect.xml?RCKSK0410370"

    data = {
        ATTR_ENTITY_ID: entity_id,
        ATTR_COMMAND: command,
    }

    await hass.services.async_call(DOMAIN, SERVICE_GET_COMMAND, data, blocking=True)
