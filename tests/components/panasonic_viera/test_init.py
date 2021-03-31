"""Test the Panasonic Viera setup process."""
from unittest.mock import Mock, patch

from homeassistant.components.panasonic_viera.const import (
    ATTR_DEVICE_INFO,
    ATTR_FRIENDLY_NAME,
    ATTR_MANUFACTURER,
    ATTR_MODEL_NUMBER,
    ATTR_UDN,
    CONF_APP_ID,
    CONF_ENCRYPTION_KEY,
    CONF_ON_ACTION,
    DEFAULT_MANUFACTURER,
    DEFAULT_MODEL_NUMBER,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
)
from homeassistant.config_entries import ENTRY_STATE_NOT_LOADED
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, STATE_UNAVAILABLE
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

MOCK_DEVICE_INFO = {
    ATTR_FRIENDLY_NAME: DEFAULT_NAME,
    ATTR_MANUFACTURER: DEFAULT_MANUFACTURER,
    ATTR_MODEL_NUMBER: DEFAULT_MODEL_NUMBER,
    ATTR_UDN: "mock-unique-id",
}


def get_mock_remote(device_info=MOCK_DEVICE_INFO):
    """Return a mock remote."""
    mock_remote = Mock()

    async def async_create_remote_control(during_setup=False):
        return

    mock_remote.async_create_remote_control = async_create_remote_control

    async def async_get_device_info():
        return device_info

    mock_remote.async_get_device_info = async_get_device_info

    return mock_remote


async def test_setup_entry_encrypted(hass):
    """Test setup with encrypted config entry."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_DEVICE_INFO[ATTR_UDN],
        data={**MOCK_CONFIG_DATA, **MOCK_ENCRYPTION_DATA, **MOCK_DEVICE_INFO},
    )

    mock_entry.add_to_hass(hass)

    mock_remote = get_mock_remote()

    with patch(
        "homeassistant.components.panasonic_viera.Remote",
        return_value=mock_remote,
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("media_player.panasonic_viera_tv")

        assert state
        assert state.name == DEFAULT_NAME


async def test_setup_entry_encrypted_missing_device_info(hass):
    """Test setup with encrypted config entry and missing device info."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_CONFIG_DATA[CONF_HOST],
        data={**MOCK_CONFIG_DATA, **MOCK_ENCRYPTION_DATA},
    )

    mock_entry.add_to_hass(hass)

    mock_remote = get_mock_remote()

    with patch(
        "homeassistant.components.panasonic_viera.Remote",
        return_value=mock_remote,
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_entry.data[ATTR_DEVICE_INFO] == MOCK_DEVICE_INFO
        assert mock_entry.unique_id == MOCK_DEVICE_INFO[ATTR_UDN]

        state = hass.states.get("media_player.panasonic_viera_tv")

        assert state
        assert state.name == DEFAULT_NAME


async def test_setup_entry_encrypted_missing_device_info_none(hass):
    """Test setup with encrypted config entry and device info set to None."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_CONFIG_DATA[CONF_HOST],
        data={**MOCK_CONFIG_DATA, **MOCK_ENCRYPTION_DATA},
    )

    mock_entry.add_to_hass(hass)

    mock_remote = get_mock_remote(device_info=None)

    with patch(
        "homeassistant.components.panasonic_viera.Remote",
        return_value=mock_remote,
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_entry.data[ATTR_DEVICE_INFO] is None
        assert mock_entry.unique_id == MOCK_CONFIG_DATA[CONF_HOST]

        state = hass.states.get("media_player.panasonic_viera_tv")

        assert state
        assert state.name == DEFAULT_NAME


async def test_setup_entry_unencrypted(hass):
    """Test setup with unencrypted config entry."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_DEVICE_INFO[ATTR_UDN],
        data={**MOCK_CONFIG_DATA, **MOCK_DEVICE_INFO},
    )

    mock_entry.add_to_hass(hass)

    mock_remote = get_mock_remote()

    with patch(
        "homeassistant.components.panasonic_viera.Remote",
        return_value=mock_remote,
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("media_player.panasonic_viera_tv")

        assert state
        assert state.name == DEFAULT_NAME


async def test_setup_entry_unencrypted_missing_device_info(hass):
    """Test setup with unencrypted config entry and missing device info."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_CONFIG_DATA[CONF_HOST],
        data=MOCK_CONFIG_DATA,
    )

    mock_entry.add_to_hass(hass)

    mock_remote = get_mock_remote()

    with patch(
        "homeassistant.components.panasonic_viera.Remote",
        return_value=mock_remote,
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_entry.data[ATTR_DEVICE_INFO] == MOCK_DEVICE_INFO
        assert mock_entry.unique_id == MOCK_DEVICE_INFO[ATTR_UDN]

        state = hass.states.get("media_player.panasonic_viera_tv")

        assert state
        assert state.name == DEFAULT_NAME


async def test_setup_entry_unencrypted_missing_device_info_none(hass):
    """Test setup with unencrypted config entry and device info set to None."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_CONFIG_DATA[CONF_HOST],
        data=MOCK_CONFIG_DATA,
    )

    mock_entry.add_to_hass(hass)

    mock_remote = get_mock_remote(device_info=None)

    with patch(
        "homeassistant.components.panasonic_viera.Remote",
        return_value=mock_remote,
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_entry.data[ATTR_DEVICE_INFO] is None
        assert mock_entry.unique_id == MOCK_CONFIG_DATA[CONF_HOST]

        state = hass.states.get("media_player.panasonic_viera_tv")

        assert state
        assert state.name == DEFAULT_NAME


async def test_setup_config_flow_initiated(hass):
    """Test if config flow is initiated in setup."""
    assert (
        await async_setup_component(
            hass,
            DOMAIN,
            {DOMAIN: {CONF_HOST: "0.0.0.0"}},
        )
        is True
    )

    assert len(hass.config_entries.flow.async_progress()) == 1


async def test_setup_unload_entry(hass):
    """Test if config entry is unloaded."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN, unique_id=MOCK_DEVICE_INFO[ATTR_UDN], data=MOCK_CONFIG_DATA
    )

    mock_entry.add_to_hass(hass)

    mock_remote = get_mock_remote()

    with patch(
        "homeassistant.components.panasonic_viera.Remote",
        return_value=mock_remote,
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    await hass.config_entries.async_unload(mock_entry.entry_id)
    assert mock_entry.state == ENTRY_STATE_NOT_LOADED
    state = hass.states.get("media_player.panasonic_viera_tv")
    assert state.state == STATE_UNAVAILABLE

    await hass.config_entries.async_remove(mock_entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get("media_player.panasonic_viera_tv")
    assert state is None
