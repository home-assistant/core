"""Tests for the SolarEdge integration."""

from unittest.mock import AsyncMock, Mock

from aiohttp import ClientError

from homeassistant.components.recorder import Recorder
from homeassistant.components.solaredge.const import CONF_SITE_ID, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .conftest import API_KEY, PASSWORD, SITE_ID, USERNAME

from tests.common import MockConfigEntry


async def test_setup_unload_api_key(
    recorder_mock: Recorder, hass: HomeAssistant, solaredge_api: Mock
) -> None:
    """Test successful setup and unload of a config entry with API key."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_SITE_ID: SITE_ID, CONF_API_KEY: API_KEY},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert solaredge_api.get_details.await_count == 2

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_unload_web_login(
    recorder_mock: Recorder, hass: HomeAssistant, solaredge_web_api: AsyncMock
) -> None:
    """Test successful setup and unload of a config entry with web login."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SITE_ID: SITE_ID,
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    solaredge_web_api.async_get_equipment.assert_awaited_once()
    solaredge_web_api.async_get_energy_data.assert_awaited_once()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_unload_both(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    solaredge_api: Mock,
    solaredge_web_api: AsyncMock,
) -> None:
    """Test successful setup and unload of a config entry with both auth methods."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SITE_ID: SITE_ID,
            CONF_API_KEY: API_KEY,
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert solaredge_api.get_details.await_count == 2
    solaredge_web_api.async_get_equipment.assert_awaited_once()
    solaredge_web_api.async_get_energy_data.assert_awaited_once()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_api_key_config_not_ready(
    recorder_mock: Recorder, hass: HomeAssistant, solaredge_api: Mock
) -> None:
    """Test for setup failure with API key."""
    solaredge_api.get_details.side_effect = ClientError()
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_SITE_ID: SITE_ID, CONF_API_KEY: API_KEY},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_web_login_config_not_ready(
    recorder_mock: Recorder, hass: HomeAssistant, solaredge_web_api: AsyncMock
) -> None:
    """Test for setup failure with web login."""
    solaredge_web_api.async_get_equipment.side_effect = ClientError()
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SITE_ID: SITE_ID,
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
