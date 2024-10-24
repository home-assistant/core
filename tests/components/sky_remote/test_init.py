"""Tests for the Sky Remote component."""

from homeassistant.components.sky_remote.const import DEFAULT_PORT, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(hass: HomeAssistant, mock_remote_control) -> None:
    """Test successful setup of entry."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "example.com",
            CONF_PORT: DEFAULT_PORT,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    entity = hass.config_entries.async_entries(DOMAIN)[0]
    assert entity.runtime_data is mock_remote_control.last_created_instance
    mock_remote_control.assert_called_once_with("example.com", DEFAULT_PORT)


async def test_setup_unconnectable_entry(
    hass: HomeAssistant, mock_remote_control_unconnectable, sample_config
) -> None:
    """Test unsuccessful setup of entry."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=sample_config,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant, sample_config, mock_remote_control
) -> None:
    """Test unload an entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=sample_config,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
