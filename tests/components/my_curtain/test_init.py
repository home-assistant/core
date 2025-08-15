import pytest
from unittest.mock import patch
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.my_curtain import (
    async_setup_entry,
    async_unload_entry,
    update_listener,
    DOMAIN,
    PLATFORMS,
)
from homeassistant.components.my_curtain.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.components.my_curtain.api import MyCurtainApiClient


@pytest.mark.asyncio
async def test_async_setup_entry(hass: HomeAssistant):
    entry = ConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "test_user", CONF_PASSWORD: "test_password"},
        entry_id="test_entry_id",
    )
    with (
        patch.object(MyCurtainApiClient, "__init__", return_value=None),
        patch.object(hass.config_entries, "async_forward_entry_setups"),
        patch.object(entry, "add_update_listener"),
    ):
        result = await async_setup_entry(hass, entry)
        assert result is True
        assert entry.entry_id in hass.data[DOMAIN]


@pytest.mark.asyncio
async def test_async_unload_entry(hass: HomeAssistant):
    entry = ConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "test_user", CONF_PASSWORD: "test_password"},
        entry_id="test_entry_id",
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = "test_client"
    with patch.object(hass.config_entries, "async_unload_platforms", return_value=True):
        result = await async_unload_entry(hass, entry)
        assert result is True
        assert entry.entry_id not in hass.data[DOMAIN]


@pytest.mark.asyncio
async def test_update_listener(hass: HomeAssistant):
    entry = ConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "test_user", CONF_PASSWORD: "test_password"},
        entry_id="test_entry_id",
    )
    with patch.object(hass.config_entries, "async_reload") as mock_reload:
        await update_listener(hass, entry)
        mock_reload.assert_called_once_with(entry.entry_id)
