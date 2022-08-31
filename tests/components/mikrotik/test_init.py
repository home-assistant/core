"""Test Mikrotik setup process."""
from unittest.mock import patch

from librouteros.exceptions import ConnectionClosed, LibRouterosError
import pytest

from homeassistant.components import mikrotik
from homeassistant.components.mikrotik.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.setup import async_setup_component

from . import MOCK_DATA

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_api():
    """Mock api."""
    with patch("librouteros.create_transport"), patch(
        "librouteros.Api.readResponse"
    ) as mock_api:
        yield mock_api


async def test_setup_with_no_config(hass):
    """Test that we do not discover anything or try to set up a hub."""
    assert await async_setup_component(hass, mikrotik.DOMAIN, {}) is True
    assert mikrotik.DOMAIN not in hass.data


async def test_successful_config_entry(hass):
    """Test config entry successful setup."""
    entry = MockConfigEntry(
        domain=mikrotik.DOMAIN,
        data=MOCK_DATA,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state == ConfigEntryState.LOADED


async def test_hub_conn_error(hass, mock_api):
    """Test that a failed setup will not store the hub."""
    entry = MockConfigEntry(
        domain=mikrotik.DOMAIN,
        data=MOCK_DATA,
    )
    entry.add_to_hass(hass)

    mock_api.side_effect = ConnectionClosed

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_hub_auth_error(hass, mock_api):
    """Test that a failed setup will not store the hub."""
    entry = MockConfigEntry(
        domain=mikrotik.DOMAIN,
        data=MOCK_DATA,
    )
    entry.add_to_hass(hass)

    mock_api.side_effect = LibRouterosError("invalid user name or password")

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.SETUP_ERROR


async def test_unload_entry(hass) -> None:
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
    assert entry.entry_id not in hass.data[DOMAIN]
