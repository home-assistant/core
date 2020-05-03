"""Test the Panasonic Viera setup process."""
from unittest.mock import Mock

from asynctest import patch

from homeassistant.components.panasonic_viera.const import (
    CONF_APP_ID,
    CONF_ENCRYPTION_KEY,
    CONF_ON_ACTION,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
)
from homeassistant.config_entries import ENTRY_STATE_NOT_LOADED
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

MOCK_CONFIG_DATA = {
    CONF_HOST: "0.0.0.0",
    CONF_NAME: DEFAULT_NAME,
    CONF_PORT: DEFAULT_PORT,
    CONF_ON_ACTION: None,
}

MOCK_ENCRYPTION_DATA = {
    CONF_APP_ID: "mock-app-id",
    CONF_ENCRYPTION_KEY: "mock-encryption-key",
}


def get_mock_remote():
    """Return a mock remote."""
    mock_remote = Mock()

    async def async_create_remote_control(during_setup=False):
        return

    mock_remote.async_create_remote_control = async_create_remote_control

    return mock_remote


async def test_setup_entry_encrypted(hass):
    """Test setup with encrypted config entry."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_CONFIG_DATA[CONF_HOST],
        data={**MOCK_CONFIG_DATA, **MOCK_ENCRYPTION_DATA},
    )

    mock_entry.add_to_hass(hass)

    mock_remote = get_mock_remote()

    with patch(
        "homeassistant.components.panasonic_viera.Remote", return_value=mock_remote,
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("media_player.panasonic_viera_tv")

        assert state
        assert state.name == DEFAULT_NAME


async def test_setup_entry_unencrypted(hass):
    """Test setup with unencrypted config entry."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN, unique_id=MOCK_CONFIG_DATA[CONF_HOST], data=MOCK_CONFIG_DATA,
    )

    mock_entry.add_to_hass(hass)

    mock_remote = get_mock_remote()

    with patch(
        "homeassistant.components.panasonic_viera.Remote", return_value=mock_remote,
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("media_player.panasonic_viera_tv")

        assert state
        assert state.name == DEFAULT_NAME


async def test_setup_config_flow_initiated(hass):
    """Test if config flow is initiated in setup."""
    assert (
        await async_setup_component(hass, DOMAIN, {DOMAIN: {CONF_HOST: "0.0.0.0"}},)
        is True
    )

    assert len(hass.config_entries.flow.async_progress()) == 1


async def test_setup_unload_entry(hass):
    """Test if config entry is unloaded."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN, unique_id=MOCK_CONFIG_DATA[CONF_HOST], data=MOCK_CONFIG_DATA
    )

    mock_entry.add_to_hass(hass)

    mock_remote = get_mock_remote()

    with patch(
        "homeassistant.components.panasonic_viera.Remote", return_value=mock_remote,
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    await hass.config_entries.async_unload(mock_entry.entry_id)

    assert mock_entry.state == ENTRY_STATE_NOT_LOADED

    state = hass.states.get("media_player.panasonic_viera_tv")

    assert state is None
