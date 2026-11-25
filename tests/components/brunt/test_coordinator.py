"""Tests for the Brunt coordinator."""

import asyncio
import logging
from unittest.mock import AsyncMock, Mock

from aiohttp import ClientResponseError
from aiohttp.client_exceptions import ServerDisconnectedError
from brunt import Thing
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.brunt.const import REGULAR_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


@pytest.mark.parametrize(
    ("exception", "level"),
    [
        pytest.param(ServerDisconnectedError(), logging.INFO, id="unreachable"),
        pytest.param(
            ClientResponseError(Mock(), (), status=500),
            logging.ERROR,
            id="response_error",
        ),
    ],
)
async def test_refresh_log_level(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_brunt_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    exception: Exception,
    level: int,
) -> None:
    """Test an unreachable service is logged at info level."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_brunt_client.async_get_things.side_effect = exception
    freezer.tick(REGULAR_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert [
        record.levelno
        for record in caplog.records
        if record.name == "homeassistant.components.brunt.coordinator"
        and record.levelno > logging.DEBUG
    ] == [level]


async def test_refresh_not_found_reloads_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_brunt_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a not found response reloads the entry without leaving it unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    things = mock_brunt_client.async_get_things.return_value
    responses = iter([ClientResponseError(Mock(), (), status=401), things])

    async def get_things(force: bool = False) -> list[Thing]:
        # Yield like a network call, so the refresh runs as an entry task.
        await asyncio.sleep(0)
        response = next(responses)
        if isinstance(response, Exception):
            raise response
        return response

    mock_brunt_client.async_get_things.side_effect = get_things
    freezer.tick(REGULAR_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_brunt_client.async_get_things.call_count == 3
