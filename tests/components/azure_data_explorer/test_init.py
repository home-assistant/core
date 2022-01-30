"""Test the init functions for AEH."""
from datetime import timedelta
import logging
from unittest.mock import patch

from homeassistant.components import azure_data_explorer
from homeassistant.components.azure_data_explorer.const import (
    CONF_SEND_INTERVAL,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from .const import (
    AZURE_DATA_EXPLORER_PATH,
    BASE_CONFIG_FULL,
    BASIC_OPTIONS,
    IMPORT_CONFIG,
)

from tests.common import MockConfigEntry, async_fire_time_changed

_LOGGER = logging.getLogger(__name__)


async def test_import(hass):
    """Test the popping of the filter and further import of the config."""
    config = {
        DOMAIN: {
            "filter": {
                "include_domains": ["light"],
                "include_entity_globs": ["sensor.included_*"],
                "include_entities": ["binary_sensor.included"],
                "exclude_domains": ["light"],
                "exclude_entity_globs": ["sensor.excluded_*"],
                "exclude_entities": ["binary_sensor.excluded"],
            },
        }
    }
    config[DOMAIN].update(IMPORT_CONFIG)
    assert await async_setup_component(hass, DOMAIN, config)


async def test_filter_only_config(hass):
    """Test the popping of the filter and further import of the config."""
    config = {
        DOMAIN: {
            "filter": {
                "include_domains": ["light"],
                "include_entity_globs": ["sensor.included_*"],
                "include_entities": ["binary_sensor.included"],
                "exclude_domains": ["light"],
                "exclude_entity_globs": ["sensor.excluded_*"],
                "exclude_entities": ["binary_sensor.excluded"],
            },
        }
    }
    assert await async_setup_component(hass, DOMAIN, config)


async def test_unload_entry(hass, entry, mock_ingest_data):
    """Test being able to unload an entry.

    Queue should be empty, so adding events to the batch should not be called,
    this verifies that the unload, calls async_stop, which calls async_send and
    shuts down the hub.
    """
    assert await hass.config_entries.async_unload(entry.entry_id)
    mock_ingest_data.add.assert_not_called()
    assert entry.state == ConfigEntryState.NOT_LOADED


async def test_failed_test_connection(hass, mock_test_connection):
    """Test being able to unload an entry."""
    entry = MockConfigEntry(
        domain=azure_data_explorer.DOMAIN,
        data=BASE_CONFIG_FULL,
        title="cluster",
        options=BASIC_OPTIONS,
    )
    entry.add_to_hass(hass)
    mock_test_connection.side_effect = Exception("Unknown")
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_late_event(hass, entry_with_one_event, mock_ingest_data):
    """Test the check on late events."""
    with patch(
        f"{AZURE_DATA_EXPLORER_PATH}.utcnow",
        return_value=utcnow() + timedelta(hours=1),
    ):
        async_fire_time_changed(
            hass,
            utcnow()
            + timedelta(seconds=entry_with_one_event.options[CONF_SEND_INTERVAL]),
        )
        await hass.async_block_till_done()
        mock_ingest_data.add.assert_not_called()
