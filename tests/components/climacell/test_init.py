"""Tests for Climacell init."""
from datetime import timedelta
import logging
from unittest.mock import patch

import pytest

from homeassistant.components.climacell.config_flow import (
    _get_config_schema,
    _get_unique_id,
)
from homeassistant.components.climacell.const import DOMAIN
from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import dt as dt_util

from .const import MIN_CONFIG

from tests.common import MockConfigEntry, async_fire_time_changed

_LOGGER = logging.getLogger(__name__)


async def test_load_and_unload(
    hass: HomeAssistantType,
    climacell_config_entry_update: pytest.fixture,
) -> None:
    """Test loading and unloading entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=_get_config_schema(hass)(MIN_CONFIG),
        unique_id=_get_unique_id(hass, _get_config_schema(hass)(MIN_CONFIG)),
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(WEATHER_DOMAIN)) == 1

    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(WEATHER_DOMAIN)) == 0


async def test_update_interval(
    hass: HomeAssistantType,
    climacell_config_entry_update: pytest.fixture,
) -> None:
    """Test that update_interval changes based on number of entries."""
    now = dt_util.utcnow()
    async_fire_time_changed(hass, now)
    config = _get_config_schema(hass)(MIN_CONFIG)
    for i in range(1, 3):
        config_entry = MockConfigEntry(
            domain=DOMAIN, data=config, unique_id=_get_unique_id(hass, config) + str(i)
        )
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    with patch("homeassistant.components.climacell.ClimaCell.realtime") as mock_api:
        # First entry refresh will happen in 7 minutes due to original update interval.
        # Next refresh for this entry will happen at 20 minutes due to the update interval
        # change.
        mock_api.return_value = {}
        async_fire_time_changed(hass, now + timedelta(minutes=7))
        await hass.async_block_till_done()
        assert mock_api.call_count == 1

        # Second entry refresh will happen in 13 minutes due to the update interval set
        # when it was set up. Next refresh for this entry will happen at 26 minutes due to the
        # update interval change.
        mock_api.reset_mock()
        async_fire_time_changed(hass, now + timedelta(minutes=13))
        await hass.async_block_till_done()
        assert not mock_api.call_count == 1

        # 19 minutes should be after the first update for each config entry and before the
        # second update for the first config entry
        mock_api.reset_mock()
        async_fire_time_changed(hass, now + timedelta(minutes=19))
        await hass.async_block_till_done()
        assert not mock_api.call_count == 0
