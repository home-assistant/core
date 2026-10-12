"""Tests for REST coordinator."""

from datetime import timedelta
from http import HTTPStatus
from typing import Any

from aiohttp import ClientError

from homeassistant.components.rest import RestConfigEntry, RestData
from homeassistant.config_entries import ConfigEntryState, ConfigSubentryData
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from .conftest import async_setup_entry

from tests.common import async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_coordinator_update_failed(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    get_config_entry_data: dict[str, Any],
    get_subentry_data: list[ConfigSubentryData],
) -> None:
    """Test the coordinator when an update fails."""

    aioclient_mock.get("http://localhost", status=HTTPStatus.OK, json={"key": "on"})

    config_entry: RestConfigEntry = await async_setup_entry(
        hass, get_config_entry_data, subentries_data=get_subentry_data
    )
    await hass.async_block_till_done()
    assert config_entry.state == ConfigEntryState.LOADED
    rest: RestData = config_entry.runtime_data.rest
    assert rest.data is not None and rest.last_exception is None

    aioclient_mock.clear_requests()
    aioclient_mock.get("http://localhost", exc=ClientError("bad request"))

    async_fire_time_changed(hass, utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done()

    assert "bad request" in str(config_entry.runtime_data.last_exception)
