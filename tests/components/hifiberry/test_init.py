"""Test the HiFiBerry integration setup."""

from unittest.mock import MagicMock

from aiohifiberry import AudioControlError

from homeassistant.components.hifiberry.const import DEFAULT_PORT, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_audiocontrol_client: MagicMock,
) -> None:
    """Test setting up a config entry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_audiocontrol_client.async_update.assert_awaited()


async def test_setup_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_audiocontrol_client: MagicMock,
) -> None:
    """Test setup retries when the player is offline."""
    mock_audiocontrol_client.async_update.side_effect = AudioControlError
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_audiocontrol_client: MagicMock,
) -> None:
    """Test unloading a config entry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_migrate_entry(
    hass: HomeAssistant,
    mock_audiocontrol_client: MagicMock,
) -> None:
    """Test legacy socket.io config entries are migrated."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Kitchen Speaker",
        data={CONF_HOST: "hifiberry.local", CONF_PORT: 81, "authtoken": "abc"},
        version=1,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 2
    assert entry.data == {CONF_HOST: "hifiberry.local", CONF_PORT: DEFAULT_PORT}
    mock_audiocontrol_client.async_update.assert_awaited()
