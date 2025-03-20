"""Tests for the Modern Forms integration."""

from unittest.mock import MagicMock, patch

from aiomodernforms import ModernFormsConnectionError

from homeassistant.components.modern_forms.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration, modern_forms_no_light_call_mock

from tests.test_util.aiohttp import AiohttpClientMocker


@patch(
    "homeassistant.components.modern_forms.coordinator.ModernFormsDevice.update",
    side_effect=ModernFormsConnectionError,
)
async def test_config_entry_not_ready(
    mock_update: MagicMock, hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the Modern Forms configuration entry not ready."""
    entry = await init_integration(hass, aioclient_mock)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_config_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the Modern Forms configuration entry unloading."""
    entry = await init_integration(hass, aioclient_mock)
    assert hass.data[DOMAIN]

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert not hass.data.get(DOMAIN)


async def test_fan_only_device(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test we set unique ID if not set yet."""
    await init_integration(
        hass, aioclient_mock, mock_type=modern_forms_no_light_call_mock
    )

    fan_entry = entity_registry.async_get("fan.modernformsfan_fan")
    assert fan_entry
    light_entry = entity_registry.async_get("light.modernformsfan_light")
    assert light_entry is None
