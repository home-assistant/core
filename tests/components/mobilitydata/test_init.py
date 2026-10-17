"""Test MobilityData integration setup and teardown."""

from datetime import timedelta
from unittest.mock import MagicMock

from aiomobilitydatabase import (
    MobilityDatabaseAuthenticationError,
    MobilityDatabaseConnectionError,
)
from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.mobilitydata.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import FEED_ID, setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed

NEXT_DEPARTURE_ENTITY = "sensor.1st_grand_next_departure"


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_handle: MagicMock,
) -> None:
    """Test a full setup and unload cycle."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_feeds_client.get_transit_feed.assert_awaited_once_with(FEED_ID, None)
    assert hass.states.get(NEXT_DEPARTURE_ENTITY) is not None

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_handle.close.assert_called_once()
    mock_feeds_client.close.assert_awaited()


async def test_remove_entry_purges_cache(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test removing the entry purges the cached dataset."""
    await setup_integration(hass, mock_config_entry)
    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_feeds_client.purge_cache.assert_awaited_once_with(FEED_ID)


async def test_setup_survives_offline_catalog(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test setup completes with unavailable entities when the catalog is down."""
    mock_feeds_client.get_transit_feed.side_effect = MobilityDatabaseConnectionError(
        "offline"
    )
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    state = hass.states.get(NEXT_DEPARTURE_ENTITY)
    assert state is not None
    assert state.state == "unavailable"

    # A scheduled arrivals poll before the handle exists also fails cleanly.
    freezer.tick(timedelta(minutes=5, seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(NEXT_DEPARTURE_ENTITY).state == "unavailable"


async def test_auth_failure_starts_reauth(
    hass: HomeAssistant,
    mock_feeds_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an invalid token during the first refresh starts reauth."""
    mock_feeds_client.get_transit_feed.side_effect = (
        MobilityDatabaseAuthenticationError("expired")
    )
    await setup_integration(hass, mock_config_entry)
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
