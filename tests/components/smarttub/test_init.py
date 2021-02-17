"""Test smarttub setup process."""

import asyncio
from unittest.mock import patch

import pytest
from smarttub import LoginFailed

from homeassistant.components import smarttub
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.setup import async_setup_component


async def test_setup_with_no_config(setup_component, hass, smarttub_api):
    """Test that we do not discover anything."""

    # No flows started
    assert len(hass.config_entries.flow.async_progress()) == 0

    smarttub_api.login.assert_not_called()


async def test_setup_entry_not_ready(setup_component, hass, config_entry, smarttub_api):
    """Test setup when the entry is not ready."""
    smarttub_api.login.side_effect = asyncio.TimeoutError

    with pytest.raises(ConfigEntryNotReady):
        await smarttub.async_setup_entry(hass, config_entry)


async def test_setup_auth_failed(setup_component, hass, config_entry, smarttub_api):
    """Test setup when the credentials are invalid."""
    smarttub_api.login.side_effect = LoginFailed

    assert await smarttub.async_setup_entry(hass, config_entry) is False


async def test_config_passed_to_config_entry(
    hass, config_entry, config_data, smarttub_api
):
    """Test that configured options are loaded via config entry."""
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, smarttub.DOMAIN, config_data)


async def test_unload_entry(hass, config_entry, smarttub_api):
    """Test being able to unload an entry."""
    config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, smarttub.DOMAIN, {}) is True

    assert await smarttub.async_unload_entry(hass, config_entry)

    # test failure of platform unload
    assert await async_setup_component(hass, smarttub.DOMAIN, {}) is True
    with patch.object(hass.config_entries, "async_forward_entry_unload") as mock:
        mock.return_value = False
        assert await smarttub.async_unload_entry(hass, config_entry) is False
