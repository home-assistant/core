"""Tests for the Gree Integration."""
import pytest

from homeassistant.components.gree.const import DOMAIN as GREE_DOMAIN
from homeassistant.config_entries import ENTRY_STATE_LOADED, ENTRY_STATE_NOT_LOADED
from homeassistant.setup import async_setup_component

from .common import MockDiscovery, build_device_mock

from tests.async_mock import patch
from tests.common import MockConfigEntry


@pytest.fixture(autouse=True, name="discovery")
def discovery_fixture(hass):
    """Patch the discovery service."""
    with patch("homeassistant.components.gree.Discovery") as mock:
        mock.return_value = MockDiscovery([build_device_mock()])
        yield mock


async def test_setup_simple(hass, discovery, device):
    """Test gree integration is setup."""
    await async_setup_component(hass, GREE_DOMAIN, {})
    await hass.async_block_till_done()

    # No flows started
    assert len(hass.config_entries.flow.async_progress()) == 0


async def test_unload_config_entry(hass, discovery, device):
    """Test that the async_unload_entry works."""
    # As we have currently no configuration, we just to pass the domain here.
    entry = MockConfigEntry(domain=GREE_DOMAIN)
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.gree.climate.async_setup_entry",
        return_value=True,
    ) as climate_setup, patch(
        "homeassistant.components.gree.switch.async_setup_entry",
        return_value=True,
    ) as switch_setup:
        assert await async_setup_component(hass, GREE_DOMAIN, {})
        await hass.async_block_till_done()

        assert len(climate_setup.mock_calls) == 1
        assert len(switch_setup.mock_calls) == 1
        assert entry.state == ENTRY_STATE_LOADED

    await hass.config_entries.async_unload(entry.entry_id)

    assert entry.state == ENTRY_STATE_NOT_LOADED
