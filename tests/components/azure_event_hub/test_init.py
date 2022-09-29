"""Test the init functions for AEH."""
from datetime import timedelta
import logging
from unittest.mock import patch

from azure.eventhub.exceptions import EventHubError
import pytest

from homeassistant.components import azure_event_hub
from homeassistant.components.azure_event_hub.const import CONF_SEND_INTERVAL, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_ON
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from .conftest import FilterTest
from .const import AZURE_EVENT_HUB_PATH, BASIC_OPTIONS, CS_CONFIG_FULL, SAS_CONFIG_FULL

from tests.common import MockConfigEntry, async_fire_time_changed

_LOGGER = logging.getLogger(__name__)


async def test_import(hass):
    """Test the popping of the filter and further import of the config."""
    config = {
        DOMAIN: {
            "send_interval": 10,
            "max_delay": 10,
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
    config[DOMAIN].update(CS_CONFIG_FULL)
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


async def test_unload_entry(hass, entry, mock_create_batch):
    """Test being able to unload an entry.

    Queue should be empty, so adding events to the batch should not be called,
    this verifies that the unload, calls async_stop, which calls async_send and
    shuts down the hub.
    """
    assert await hass.config_entries.async_unload(entry.entry_id)
    mock_create_batch.add.assert_not_called()
    assert entry.state == ConfigEntryState.NOT_LOADED


async def test_failed_test_connection(hass, mock_get_eventhub_properties):
    """Test being able to unload an entry."""
    entry = MockConfigEntry(
        domain=azure_event_hub.DOMAIN,
        data=SAS_CONFIG_FULL,
        title="test-instance",
        options=BASIC_OPTIONS,
    )
    entry.add_to_hass(hass)
    mock_get_eventhub_properties.side_effect = EventHubError("Test")
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_send_batch_error(hass, entry_with_one_event, mock_send_batch):
    """Test a error in send_batch, including recovering at the next interval."""
    mock_send_batch.reset_mock()
    mock_send_batch.side_effect = [EventHubError("Test"), None]
    async_fire_time_changed(
        hass,
        utcnow() + timedelta(seconds=entry_with_one_event.options[CONF_SEND_INTERVAL]),
    )
    await hass.async_block_till_done()
    mock_send_batch.assert_called_once()
    mock_send_batch.reset_mock()
    hass.states.async_set("sensor.test2", STATE_ON)
    async_fire_time_changed(
        hass,
        utcnow() + timedelta(seconds=entry_with_one_event.options[CONF_SEND_INTERVAL]),
    )
    await hass.async_block_till_done()
    mock_send_batch.assert_called_once()


async def test_late_event(hass, entry_with_one_event, mock_create_batch):
    """Test the check on late events."""
    with patch(
        f"{AZURE_EVENT_HUB_PATH}.utcnow",
        return_value=utcnow() + timedelta(hours=1),
    ):
        async_fire_time_changed(
            hass,
            utcnow()
            + timedelta(seconds=entry_with_one_event.options[CONF_SEND_INTERVAL]),
        )
        await hass.async_block_till_done()
        mock_create_batch.add.assert_not_called()


async def test_full_batch(hass, entry_with_one_event, mock_create_batch):
    """Test the full batch behaviour."""
    mock_create_batch.add.side_effect = [ValueError, None]
    async_fire_time_changed(
        hass,
        utcnow() + timedelta(seconds=entry_with_one_event.options[CONF_SEND_INTERVAL]),
    )
    await hass.async_block_till_done()
    assert mock_create_batch.add.call_count == 2


@pytest.mark.parametrize(
    "filter_schema, tests",
    [
        (
            {
                "include_domains": ["light"],
                "include_entity_globs": ["sensor.included_*"],
                "include_entities": ["binary_sensor.included"],
            },
            [
                FilterTest("climate.excluded", 0),
                FilterTest("light.included", 1),
                FilterTest("sensor.excluded_test", 0),
                FilterTest("sensor.included_test", 1),
                FilterTest("binary_sensor.included", 1),
                FilterTest("binary_sensor.excluded", 0),
            ],
        ),
        (
            {
                "exclude_domains": ["climate"],
                "exclude_entity_globs": ["sensor.excluded_*"],
                "exclude_entities": ["binary_sensor.excluded"],
            },
            [
                FilterTest("climate.excluded", 0),
                FilterTest("light.included", 1),
                FilterTest("sensor.excluded_test", 0),
                FilterTest("sensor.included_test", 1),
                FilterTest("binary_sensor.included", 1),
                FilterTest("binary_sensor.excluded", 0),
            ],
        ),
        (
            {
                "include_domains": ["light"],
                "include_entity_globs": ["*.included_*"],
                "exclude_domains": ["climate"],
                "exclude_entity_globs": ["*.excluded_*"],
                "exclude_entities": ["light.excluded"],
            },
            [
                FilterTest("light.included", 1),
                FilterTest("light.excluded_test", 0),
                FilterTest("light.excluded", 0),
                FilterTest("sensor.included_test", 1),
                FilterTest("climate.included_test", 1),
            ],
        ),
        (
            {
                "include_entities": ["climate.included", "sensor.excluded_test"],
                "exclude_domains": ["climate"],
                "exclude_entity_globs": ["*.excluded_*"],
                "exclude_entities": ["light.excluded"],
            },
            [
                FilterTest("climate.excluded", 0),
                FilterTest("climate.included", 1),
                FilterTest("switch.excluded_test", 0),
                FilterTest("sensor.excluded_test", 1),
                FilterTest("light.excluded", 0),
                FilterTest("light.included", 1),
            ],
        ),
    ],
    ids=["allowlist", "denylist", "filtered_allowlist", "filtered_denylist"],
)
async def test_filter(hass, entry, tests, mock_create_batch):
    """Test different filters.

    Filter_schema is also a fixture which is replaced by the filter_schema
    in the parametrize and added to the entry fixture.
    """
    for test in tests:
        hass.states.async_set(test.entity_id, STATE_ON)
        async_fire_time_changed(
            hass, utcnow() + timedelta(seconds=entry.options[CONF_SEND_INTERVAL])
        )
        await hass.async_block_till_done()
        assert mock_create_batch.add.call_count == test.expected_count
        mock_create_batch.add.reset_mock()
