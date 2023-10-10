"""Tests for refoss component."""
from unittest.mock import patch

from homeassistant.components.refoss.const import DOMAIN as REFOSS_DOMAIN
from homeassistant.components.switch import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .common import FakeDiscovery, build_base_device_mock

from tests.common import MockConfigEntry


async def async_setup_refoss_switch(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the refoss switch platform."""
    entry = MockConfigEntry(domain=REFOSS_DOMAIN)
    entry.add_to_hass(hass)
    await async_setup_component(hass, REFOSS_DOMAIN, {REFOSS_DOMAIN: {DOMAIN: {}}})
    await hass.async_block_till_done()
    return entry


@patch("homeassistant.components.refoss.PLATFORMS", [DOMAIN])
async def test_registry_settings(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for entity registry settings."""
    with patch(
        "homeassistant.components.refoss.util.Discovery",
        return_value=FakeDiscovery(),
    ), patch(
        "homeassistant.components.refoss.bridge.async_build_base_device",
        return_value=build_base_device_mock(),
    ), patch(
        "homeassistant.components.refoss.switch.isinstance",
        return_value=True,
    ):
        entry = await async_setup_refoss_switch(hass)
        assert entry.state == ConfigEntryState.LOADED
