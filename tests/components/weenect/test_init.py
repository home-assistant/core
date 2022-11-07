"""Test weenect setup process."""
import pytest

from homeassistant.components.weenect import (
    WeenectDataUpdateCoordinator,
    async_reload_entry,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.weenect.const import DOMAIN
from homeassistant.exceptions import ConfigEntryNotReady

from .const import MOCK_CONFIG

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("bypass_get_trackers")
async def test_setup_unload_and_reload_entry(hass):
    """Test entry setup, reload and unload."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")

    assert await async_setup_entry(hass, config_entry)
    assert DOMAIN in hass.data and config_entry.entry_id in hass.data[DOMAIN]
    assert isinstance(
        hass.data[DOMAIN][config_entry.entry_id], WeenectDataUpdateCoordinator
    )

    await async_reload_entry(hass, config_entry)
    assert DOMAIN in hass.data and config_entry.entry_id in hass.data[DOMAIN]
    assert isinstance(
        hass.data[DOMAIN][config_entry.entry_id], WeenectDataUpdateCoordinator
    )

    assert await async_unload_entry(hass, config_entry)
    assert config_entry.entry_id not in hass.data[DOMAIN]


@pytest.mark.usefixtures("error_on_get_trackers")
async def test_setup_entry_exception(hass):
    """Test ConfigEntryNotReady when API raises an exception during entry setup."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")

    with pytest.raises(ConfigEntryNotReady):
        assert await async_setup_entry(hass, config_entry)
