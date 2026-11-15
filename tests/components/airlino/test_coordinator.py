"""Tests for the AirLino data update coordinator."""

import logging
from unittest.mock import MagicMock

from airlino_api import AirlinoApiConnectionError, AirlinoApiError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.airlino.const import UPDATE_INTERVAL
from homeassistant.const import STATE_PLAYING, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

ENTITY_ID = "media_player.living_room"


@pytest.mark.parametrize(
    ("exception", "log_level", "log_message"),
    [
        pytest.param(
            AirlinoApiConnectionError("offline"),
            logging.INFO,
            "AirLino is unavailable",
            id="connection_error",
        ),
        pytest.param(
            AirlinoApiError("failed"),
            logging.ERROR,
            "Error fetching AirLino data",
            id="api_error",
        ),
    ],
)
async def test_entity_unavailable_while_device_unreachable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    mock_config_entry: MockConfigEntry,
    mock_airlino_api: MagicMock,
    exception: Exception,
    log_level: int,
    log_message: str,
) -> None:
    """Mark the entity unavailable on update failures and recover afterwards."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_PLAYING

    mock_airlino_api.async_get_player_status.side_effect = exception
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    assert any(
        record.levelno == log_level and log_message in record.getMessage()
        for record in caplog.records
    )

    mock_airlino_api.async_get_player_status.side_effect = None
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_PLAYING
