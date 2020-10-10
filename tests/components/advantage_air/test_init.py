"""Test the Advantage Air Initialization."""

import pytest

from homeassistant.components.advantage_air import async_setup, async_setup_entry
from homeassistant.components.advantage_air.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from tests.common import MockConfigEntry
from tests.components.advantage_air import add_mock_config, api_response


async def test_async_setup_entry(hass, aiohttp_raw_server, aiohttp_unused_port):
    """Test a successful setup entry."""

    port = aiohttp_unused_port()
    await aiohttp_raw_server(api_response, port=port)

    assert await async_setup(hass, {})
    assert hass.data[DOMAIN] == {}
    entry = await add_mock_config(hass, port)

    assert hass.data[DOMAIN][entry.entry_id]
    assert isinstance(
        hass.data[DOMAIN][entry.entry_id]["coordinator"], DataUpdateCoordinator
    )
    assert callable(hass.data[DOMAIN][entry.entry_id]["async_change"])


async def test_async_setup_entry_failure(hass, aiohttp_unused_port):
    """Test a successful setup entry."""

    port = aiohttp_unused_port()
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="test entry",
        unique_id="0123456",
        data={
            CONF_IP_ADDRESS: "127.0.0.1",
            CONF_PORT: port,
        },
    )

    await async_setup(hass, {})
    with pytest.raises(ConfigEntryNotReady):
        await async_setup_entry(hass, entry)
