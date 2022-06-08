"""Test for Aladdin Connect init logic."""
from unittest.mock import patch

from homeassistant.components.aladdin_connect.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

YAML_CONFIG = {"username": "test-user", "password": "test-password"}


async def test_entry_password_fail(hass: HomeAssistant):
    """Test password fail during entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "test-user", "password": "test-password"},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.aladdin_connect.cover.AladdinConnectClient.login",
        return_value=False,
    ):

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_load_and_unload(hass: HomeAssistant) -> None:
    """Test loading and unloading Aladdin Connect entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=YAML_CONFIG,
        unique_id="test-id",
    )
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.aladdin_connect.cover.AladdinConnectClient.login",
        return_value=True,
    ):

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.LOADED
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    assert await config_entry.async_unload(hass)
    await hass.async_block_till_done()
    assert config_entry.state == ConfigEntryState.NOT_LOADED
