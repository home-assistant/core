"""Tests for the PubliBike component."""
from unittest.mock import patch

from homeassistant.components.publibike.const import (
    BATTERY_LIMIT,
    DOMAIN,
    LATITUDE,
    LONGITUDE,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.publibike.mocks import _get_mock_bike


async def test_load_unload_config_entry(hass: HomeAssistant) -> None:
    """Test the Publibike configuration entry loading/unloading."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            BATTERY_LIMIT: 99,
            LATITUDE: 1.0,
            LONGITUDE: 2.0,
        },
    )

    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.publibike.config_flow.PubliBike",
        return_value=_get_mock_bike(),
    ), patch(
        "homeassistant.components.publibike.PubliBike", return_value=_get_mock_bike()
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
