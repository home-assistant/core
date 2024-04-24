"""Tests for the Gree Integration."""
from unittest.mock import patch

from homeassistant.components.gree.const import DOMAIN as GREE_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_setup_simple(hass: HomeAssistant) -> None:
    """Test gree integration is setup."""
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
        assert entry.state is ConfigEntryState.LOADED

    # No flows started
    assert len(hass.config_entries.flow.async_progress()) == 0


async def test_unload_config_entry(hass: HomeAssistant) -> None:
    """Test that the async_unload_entry works."""
    # As we have currently no configuration, we just to pass the domain here.
    entry = MockConfigEntry(domain=GREE_DOMAIN)
    entry.add_to_hass(hass)

    assert await async_setup_component(hass, GREE_DOMAIN, {})
    await hass.async_block_till_done()

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
