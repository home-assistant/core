"""Test the init functions for AEH."""
from datetime import timedelta
import logging
from time import monotonic
from unittest.mock import patch

from azure.eventhub.exceptions import EventHubError
import pytest

from homeassistant.components import azure_event_hub
from homeassistant.components.azure_event_hub.const import DATA_HUB, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_ON
from homeassistant.setup import async_setup_component

from .conftest import FilterTest
from .const import AZURE_EVENT_HUB_PATH, BASIC_OPTIONS, CS_CONFIG_FULL, SAS_CONFIG_FULL

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


async def test_import(hass):
    """Test the popping of the filter and further import of the config."""
    config = {
        azure_event_hub.DOMAIN: {
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
    config[azure_event_hub.DOMAIN].update(CS_CONFIG_FULL)
    assert await async_setup_component(hass, azure_event_hub.DOMAIN, config)


async def test_filter_only_config(hass):
    """Test the popping of the filter and further import of the config."""
    config = {
        azure_event_hub.DOMAIN: {
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
    assert await async_setup_component(hass, azure_event_hub.DOMAIN, config)


async def test_unload_entry(hass, entry):
    """Test being able to unload an entry."""
    assert await hass.config_entries.async_unload(entry.entry_id)
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
    try:
        await hass.config_entries.async_setup(entry.entry_id)
    except azure_event_hub.ConfigEntryNotReady:
        pass
    assert entry.state == ConfigEntryState.SETUP_RETRY


async def test_stop(hass, hub):
    """Test stopping the hub, which empties the queue."""
    assert await hub.async_stop()
    assert hub.queue.empty()


async def test_send_batch_error(hass, hub, mock_send_batch):
    """Test a error in send_batch."""
    mock_send_batch.reset_mock()
    mock_send_batch.side_effect = EventHubError("Test")
    await hub.async_send(None)
    mock_send_batch.assert_called_once()


async def test_late_event(hass, hub, mock_create_batch):
    """Test the check on late events."""
    with patch(
        f"{AZURE_EVENT_HUB_PATH}.time.monotonic",
        return_value=monotonic() + timedelta(hours=1).seconds,
    ):
        await hub.async_send(None)
        mock_create_batch.add.assert_not_called()


async def test_full_batch(hass, hub, mock_create_batch):
    """Test the full batch behaviour.

    Can't use async_send, because that causes a loop with this side_effect.
    """
    mock_create_batch.add.side_effect = ValueError
    assert hub.queue.qsize() == 1
    async with hub._client.client as client:  # pylint: disable=protected-access
        await hub.fill_batch(client)
    assert hub.queue.qsize() == 1


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
                FilterTest("climate.excluded", False),
                FilterTest("light.included", True),
                FilterTest("sensor.excluded_test", False),
                FilterTest("sensor.included_test", True),
                FilterTest("binary_sensor.included", True),
                FilterTest("binary_sensor.excluded", False),
            ],
        ),
        (
            {
                "exclude_domains": ["climate"],
                "exclude_entity_globs": ["sensor.excluded_*"],
                "exclude_entities": ["binary_sensor.excluded"],
            },
            [
                FilterTest("climate.excluded", False),
                FilterTest("light.included", True),
                FilterTest("sensor.excluded_test", False),
                FilterTest("sensor.included_test", True),
                FilterTest("binary_sensor.included", True),
                FilterTest("binary_sensor.excluded", False),
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
                FilterTest("light.included", True),
                FilterTest("light.excluded_test", False),
                FilterTest("light.excluded", False),
                FilterTest("sensor.included_test", True),
                FilterTest("climate.included_test", False),
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
                FilterTest("climate.excluded", False),
                FilterTest("climate.included", True),
                FilterTest("switch.excluded_test", False),
                FilterTest("sensor.excluded_test", True),
                FilterTest("light.excluded", False),
                FilterTest("light.included", True),
            ],
        ),
    ],
    ids=["allowlist", "denylist", "filtered_allowlist", "filtered_denylist"],
)
async def test_filter(hass, entry, tests, mock_create_batch):
    """Test different filters.

    Filter_schema is also a fixture which is replaced by the filter_schema in the parametrize and added to the entry fixture.
    """
    for test in tests:
        hass.states.async_set(test.entity_id, STATE_ON)
        await hass.async_block_till_done()
        await hass.data[DOMAIN][DATA_HUB].async_send(None)

        if test.should_pass:
            mock_create_batch.add.assert_called_once()
            mock_create_batch.add.reset_mock()
        else:
            mock_create_batch.add.assert_not_called()
