"""Test smarttub setup process."""

import asyncio
from unittest.mock import patch

import pytest
from smarttub import LoginFailed

from homeassistant.components import smarttub
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.setup import async_setup_component


async def test_setup_with_no_config(hass):
    """Test that we do not discover anything."""
    assert await async_setup_component(hass, smarttub.DOMAIN, {}) is True

    # No flows started
    assert len(hass.config_entries.flow.async_progress()) == 0

    assert smarttub.const.SMARTTUB_CONTROLLER not in hass.data[smarttub.DOMAIN]


async def test_setup_entry_not_ready(hass, config_entry, smarttub_api):
    """Test setup when the entry is not ready."""
    assert await async_setup_component(hass, smarttub.DOMAIN, {}) is True
    smarttub_api.login.side_effect = asyncio.TimeoutError

    with pytest.raises(ConfigEntryNotReady):
        await smarttub.async_setup_entry(hass, config_entry)


async def test_setup_auth_failed(hass, config_entry, smarttub_api):
    """Test setup when the credentials are invalid."""
    assert await async_setup_component(hass, smarttub.DOMAIN, {}) is True
    smarttub_api.login.side_effect = LoginFailed

    assert await smarttub.async_setup_entry(hass, config_entry) is False


async def test_config_passed_to_config_entry(hass, config_entry, config_data):
    """Test that configured options are loaded via config entry."""
    config_entry.add_to_hass(hass)
    ret = await async_setup_component(hass, smarttub.DOMAIN, config_data)
    assert ret is True


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
