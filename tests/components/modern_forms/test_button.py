"""Tests for the Modern Forms button platform."""

from unittest.mock import patch

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration, init_integration_gen4

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_restart_button(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the creation of the restart button on a legacy fan."""
    await init_integration(hass, aioclient_mock)

    state = hass.states.get("button.modernformsfan_restart")
    assert state
    entry = entity_registry.async_get("button.modernformsfan_restart")
    assert entry
    assert entry.unique_id == "AA:BB:CC:DD:EE:FF_restart"


async def test_restart_button_gen4(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the creation of the restart button on a Gen4 fan."""
    await init_integration_gen4(hass, aioclient_mock)

    state = hass.states.get("button.modernformsfan_restart")
    assert state
    entry = entity_registry.async_get("button.modernformsfan_restart")
    assert entry
    assert entry.unique_id == "AA:BB:CC:00:11:22_restart"


async def test_restart_button_press(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test pressing the restart button."""
    await init_integration(hass, aioclient_mock)

    with patch("aiomodernforms.ModernFormsDevice.reboot") as reboot_mock:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: "button.modernformsfan_restart"},
            blocking=True,
        )
        await hass.async_block_till_done()
        reboot_mock.assert_called_once_with()
