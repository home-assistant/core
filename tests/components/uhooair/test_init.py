"""Test uHoo setup process."""

import re

import pytest

from homeassistant.components.uhooair import (
    UhooDataUpdateCoordinator,
    async_setup_entry,
)
from homeassistant.components.uhooair.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.setup import async_setup_component

from .const import MOCK_CONFIG

from tests.common import MockConfigEntry


async def test_setup_no_config(hass: HomeAssistant) -> None:
    """Test DOMAIN is empty if there is no config."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert DOMAIN not in hass.config_entries.async_domains()


async def test_async_setup_entry(
    hass: HomeAssistant,
    bypass_login,
    bypass_get_latest_data,
    bypass_get_devices,
    bypass_setup_devices,
) -> None:
    """Test a successful setup entry."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="1",
        data=MOCK_CONFIG,
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert DOMAIN in hass.data and config_entry.entry_id in hass.data[DOMAIN]
    assert type(hass.data[DOMAIN][config_entry.entry_id]) is UhooDataUpdateCoordinator


async def test_async_setup_entry_exception(hass: HomeAssistant, error_on_login) -> None:
    """Test when API raises an exception during entry setup."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)

    # Expect ConfigEntryError to be raised instead of returning False
    with pytest.raises(
        ConfigEntryError,
        match=re.escape("Unauthorized (401): Invalid API key or token."),
    ):
        await async_setup_entry(hass, config_entry)


async def test_unload_entry(
    hass: HomeAssistant,
    bypass_login,
    bypass_get_latest_data,
    bypass_get_devices,
    bypass_setup_devices,
) -> None:
    """Test successful unload of entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="1",
        data=MOCK_CONFIG,
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert config_entry.state is ConfigEntryState.LOADED

    assert DOMAIN in hass.data
    assert config_entry.entry_id in hass.data[DOMAIN]

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
