"""The tests for the KMtronic component."""
import asyncio

from homeassistant.components.kmtronic.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState

from tests.common import MockConfigEntry


async def test_unload_config_entry(hass, aioclient_mock):
    """Test entry unloading."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "1.1.1.1",
            "username": "admin",
            "password": "admin",
        },
    )
    config_entry.add_to_hass(hass)

    aioclient_mock.get(
        "http://1.1.1.1/status.xml",
        text="<response><relay0>0</relay0><relay1>0</relay1></response>",
    )
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_config_entry_not_ready(hass, aioclient_mock):
    """Tests configuration entry not ready."""

    aioclient_mock.get(
        "http://1.1.1.1/status.xml",
        exc=asyncio.TimeoutError(),
    )

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "1.1.1.1",
            "username": "foo",
            "password": "bar",
        },
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
