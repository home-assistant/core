"""Tests for Renault setup process."""
from unittest.mock import patch

import aiohttp
import pytest

from homeassistant.components.renault import (
    RenaultHub,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.renault.const import DOMAIN
from homeassistant.exceptions import ConfigEntryNotReady

from .const import MOCK_CONFIG

from tests.common import MockConfigEntry


async def test_setup_unload_and_reload_entry(hass):
    """Test entry setup and unload."""
    # Create a mock entry so we don't have to go through config flow
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=123456
    )

    with patch(
        "homeassistant.components.renault.RenaultHub.attempt_login", return_value=True
    ), patch("homeassistant.components.renault.RenaultHub.async_initialise"):
        # Set up the entry and assert that the values set during setup are where we expect
        # them to be.
        assert await async_setup_entry(hass, config_entry)
        assert DOMAIN in hass.data and config_entry.unique_id in hass.data[DOMAIN]
        assert isinstance(hass.data[DOMAIN][config_entry.unique_id], RenaultHub)

        # Unload the entry and verify that the data has been removed
        assert await async_unload_entry(hass, config_entry)
        assert config_entry.unique_id not in hass.data[DOMAIN]


async def test_setup_entry_bad_password(hass):
    """Test entry setup and unload."""
    # Create a mock entry so we don't have to go through config flow
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=123456
    )

    with patch(
        "homeassistant.components.renault.RenaultHub.attempt_login", return_value=False
    ):
        # Set up the entry and assert that the values set during setup are where we expect
        # them to be.
        assert not await async_setup_entry(hass, config_entry)


async def test_setup_entry_exception(hass):
    """Test ConfigEntryNotReady when API raises an exception during entry setup."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=123456
    )

    # In this case we are testing the condition where async_setup_entry raises
    # ConfigEntryNotReady.
    with patch(
        "homeassistant.components.renault.RenaultHub.attempt_login",
        side_effect=aiohttp.ClientConnectionError,
    ), pytest.raises(ConfigEntryNotReady):
        assert await async_setup_entry(hass, config_entry)
