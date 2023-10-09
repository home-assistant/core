"""Tests for the refoss Integration."""
from unittest.mock import patch

from homeassistant.components.refoss.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import FakeDiscovery, build_base_device_mock

from tests.common import MockConfigEntry


async def test_setup_simple(hass: HomeAssistant) -> None:
    """Test refoss integration is setup."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.refoss.refoss_discovery_server",
        return_value=FakeDiscovery(),
    ), patch(
        "homeassistant.components.refoss.bridge.async_build_base_device",
        return_value=build_base_device_mock(),
    ), patch(
        "homeassistant.components.refoss.switch.async_setup_entry",
        return_value=True,
    ) as switch_setup:
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()

        assert len(switch_setup.mock_calls) == 1

        assert entry.state is ConfigEntryState.LOADED


async def test_unload_config_entry(hass: HomeAssistant) -> None:
    """Test that the async_unload_entry works."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
