"""Test setting up and unloading PrusaLink."""
from datetime import timedelta
from unittest.mock import patch

from pyprusalink import InvalidAuth, PrusaLinkError
import pytest

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from tests.common import async_fire_time_changed


async def test_unloading(
    hass: HomeAssistant,
    mock_config_entry: ConfigEntry,
    mock_api,
):
    """Test unloading prusalink."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state == ConfigEntryState.LOADED

    assert hass.states.async_entity_ids_count() > 0

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state == ConfigEntryState.NOT_LOADED

    for state in hass.states.async_all():
        assert state.state == "unavailable"


@pytest.mark.parametrize("exception", [InvalidAuth, PrusaLinkError])
async def test_failed_update(
    hass: HomeAssistant, mock_config_entry: ConfigEntry, mock_api, exception
):
    """Test failed update marks prusalink unavailable."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state == ConfigEntryState.LOADED

    with patch(
        "homeassistant.components.prusalink.PrusaLink.get_printer",
        side_effect=exception,
    ), patch(
        "homeassistant.components.prusalink.PrusaLink.get_job",
        side_effect=exception,
    ):
        async_fire_time_changed(hass, utcnow() + timedelta(seconds=30), fire_all=True)
        await hass.async_block_till_done()

    for state in hass.states.async_all():
        assert state.state == "unavailable"
