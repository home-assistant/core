"""Test for Aladdin Connect init logic."""
from unittest.mock import patch

from homeassistant.components.aladdin_connect.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_unload_entry(hass: HomeAssistant):
    """Test successful unload of entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "test-user", "password": "test-password"},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.aladdin_connect.cover.AladdinConnectClient.login",
        return_value=True,
    ):

        assert (await async_setup_component(hass, DOMAIN, entry)) is True

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_entry_password_fail(hass: HomeAssistant):
    """Test successful unload of entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "test-user", "password": "test-password"},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.aladdin_connect.cover.AladdinConnectClient.login",
        return_value=False,
    ):

        assert (await async_setup_component(hass, DOMAIN, entry)) is True
