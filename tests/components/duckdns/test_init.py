"""Test the DuckDNS component."""

from datetime import timedelta
import logging

import pytest

from homeassistant.components.duckdns import (
    ATTR_TXT,
    BACKOFF_INTERVALS,
    DOMAIN,
    INTERVAL,
    SERVICE_SET_TXT,
    UPDATE_URL,
    async_track_time_interval_backoff,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from .conftest import TEST_SUBDOMAIN, TEST_TOKEN

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker

_LOGGER = logging.getLogger(__name__)


async def async_set_txt(hass: HomeAssistant, txt: str | None) -> None:
    """Set the txt record. Pass in None to remove it.

    This is a legacy helper method. Do not use it for new tests.
    """
    await hass.services.async_call(
        DOMAIN, SERVICE_SET_TXT, {ATTR_TXT: txt}, blocking=True
    )


@pytest.fixture
async def setup_duckdns(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
) -> None:
    """Fixture that sets up DuckDNS."""

    aioclient_mock.get(
        UPDATE_URL,
        params={"domains": TEST_SUBDOMAIN, "token": TEST_TOKEN},
        text="OK",
    )

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("setup_duckdns")
async def test_setup(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Test setup works if update passes."""
    aioclient_mock.get(
        UPDATE_URL,
        params={"domains": TEST_SUBDOMAIN, "token": TEST_TOKEN},
        text="OK",
    )

    assert aioclient_mock.call_count == 1

    async_fire_time_changed(hass, utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 2


async def test_setup_backoff(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
) -> None:
    """Test setup fails if first update fails."""
    aioclient_mock.get(
        UPDATE_URL,
        params={"domains": TEST_SUBDOMAIN, "token": TEST_TOKEN},
        text="KO",
    )

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert aioclient_mock.call_count == 1

    tme = utcnow()
    await hass.async_block_till_done()

    _LOGGER.debug("Backoff")
    for idx in range(1, len(BACKOFF_INTERVALS)):
        tme += BACKOFF_INTERVALS[idx]
        async_fire_time_changed(hass, tme)
        await hass.async_block_till_done()

        assert aioclient_mock.call_count == idx + 1


@pytest.mark.usefixtures("setup_duckdns")
async def test_service_set_txt(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test set txt service call."""
    # Empty the fixture mock requests
    aioclient_mock.clear_requests()

    aioclient_mock.get(
        UPDATE_URL,
        params={"domains": TEST_SUBDOMAIN, "token": TEST_TOKEN, "txt": "some-txt"},
        text="OK",
    )

    assert aioclient_mock.call_count == 0
    await async_set_txt(hass, "some-txt")
    assert aioclient_mock.call_count == 1


@pytest.mark.usefixtures("setup_duckdns")
async def test_service_clear_txt(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test clear txt service call."""
    # Empty the fixture mock requests
    aioclient_mock.clear_requests()

    aioclient_mock.get(
        UPDATE_URL,
        params={
            "domains": TEST_SUBDOMAIN,
            "token": TEST_TOKEN,
            "txt": "",
            "clear": "true",
        },
        text="OK",
    )

    assert aioclient_mock.call_count == 0
    await async_set_txt(hass, None)
    assert aioclient_mock.call_count == 1


async def test_async_track_time_interval_backoff(hass: HomeAssistant) -> None:
    """Test setup fails if first update fails."""
    ret_val = False
    call_count = 0
    tme = None

    async def _return(now):
        nonlocal call_count, ret_val, tme
        if tme is None:
            tme = now
        call_count += 1
        return ret_val

    intervals = (
        INTERVAL,
        INTERVAL * 2,
        INTERVAL * 5,
        INTERVAL * 9,
        INTERVAL * 10,
        INTERVAL * 11,
        INTERVAL * 12,
    )

    async_track_time_interval_backoff(hass, _return, intervals)
    await hass.async_block_till_done()

    assert call_count == 1

    _LOGGER.debug("Backoff")
    for idx in range(1, len(intervals)):
        tme += intervals[idx]
        async_fire_time_changed(hass, tme + timedelta(seconds=0.1))
        await hass.async_block_till_done()

        assert call_count == idx + 1

    _LOGGER.debug("Max backoff reached - intervals[-1]")
    for _idx in range(1, 10):
        tme += intervals[-1]
        async_fire_time_changed(hass, tme + timedelta(seconds=0.1))
        await hass.async_block_till_done()

        assert call_count == idx + 1 + _idx

    _LOGGER.debug("Reset backoff")
    call_count = 0
    ret_val = True
    tme += intervals[-1]
    async_fire_time_changed(hass, tme + timedelta(seconds=0.1))
    await hass.async_block_till_done()
    assert call_count == 1

    _LOGGER.debug("No backoff - intervals[0]")
    for _idx in range(2, 10):
        tme += intervals[0]
        async_fire_time_changed(hass, tme + timedelta(seconds=0.1))
        await hass.async_block_till_done()

        assert call_count == _idx


async def test_load_unload(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test loading and unloading of the config entry."""

    aioclient_mock.get(
        UPDATE_URL,
        params={"domains": TEST_SUBDOMAIN, "token": TEST_TOKEN},
        text="OK",
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED
