"""Test Mikrotik setup process."""
import librouteros

from homeassistant.components import mikrotik
from homeassistant.components.mikrotik.const import (
    CLIENTS,
    CONF_DHCP_SERVER_TRACK_MODE,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import MOCK_DATA, MOCK_DATA_OLD, MOCK_OPTIONS_OLD

from tests.common import MockConfigEntry
from tests.components.mikrotik.test_hub import setup_mikrotik_entry


async def test_setup_with_no_config(hass):
    """Test that we do not discover anything or try to set up a hub."""
    assert await async_setup_component(hass, mikrotik.DOMAIN, {}) is True
    assert mikrotik.DOMAIN not in hass.data


async def test_successful_config_entry(hass: HomeAssistant) -> None:
    """Test config entry successful setup."""
    entry = MockConfigEntry(
        domain=mikrotik.DOMAIN,
        data=MOCK_DATA,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state == ConfigEntryState.LOADED
    assert hass.data[DOMAIN][entry.entry_id]
    assert CLIENTS in hass.data[DOMAIN]


async def test_old_config_entry_update(hass: HomeAssistant) -> None:
    """Test config entry successful setup."""
    entry = MockConfigEntry(
        domain=mikrotik.DOMAIN,
        title=MOCK_DATA_OLD[CONF_NAME],
        data=MOCK_DATA_OLD,
        options=MOCK_OPTIONS_OLD,
    )
    entry.add_to_hass(hass)

    await setup_mikrotik_entry(hass, entry)
    assert entry.state == ConfigEntryState.LOADED
    assert hass.data[DOMAIN][entry.entry_id]
    assert entry.unique_id == entry.data[CONF_HOST]
    assert entry.title == "router (0.0.0.1)"
    assert entry.options[CONF_DHCP_SERVER_TRACK_MODE] == "ARP ping"


async def test_hub_connection_error(hass: HomeAssistant, mock_api):
    """Test setup retry due to connection error."""
    entry = MockConfigEntry(
        domain=mikrotik.DOMAIN,
        data=MOCK_DATA,
    )
    entry.add_to_hass(hass)

    mock_api.side_effect = librouteros.exceptions.ConnectionClosed

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_hub_auth_error(hass: HomeAssistant, mock_api):
    """Test setup fails due to auth error."""
    entry = MockConfigEntry(
        domain=mikrotik.DOMAIN,
        data=MOCK_DATA,
    )
    entry.add_to_hass(hass)

    mock_api.side_effect = librouteros.exceptions.TrapError(
        "invalid user name or password"
    )

    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state == ConfigEntryState.SETUP_ERROR


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test being able to unload an entry."""
    entry = MockConfigEntry(
        domain=mikrotik.DOMAIN,
        data=MOCK_DATA,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.NOT_LOADED
    assert DOMAIN not in hass.data
