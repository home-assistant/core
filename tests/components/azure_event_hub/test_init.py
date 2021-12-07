"""Test the init functions for AEH."""
from dataclasses import dataclass
from datetime import timedelta
import logging
from unittest.mock import patch

from azure.eventhub.exceptions import EventHubError
import pytest

from homeassistant.components import azure_event_hub
from homeassistant.components.azure_event_hub import AzureEventHub
from homeassistant.components.azure_event_hub.const import (
    CONF_MAX_DELAY,
    CONF_SEND_INTERVAL,
    DATA_FILTER,
    DOMAIN,
)
from homeassistant.const import STATE_ON
from homeassistant.helpers.entityfilter import FILTER_SCHEMA
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from .const import (
    AZURE_EVENT_HUB_PATH,
    BASIC_OPTIONS,
    CS_CONFIG_FULL,
    PRODUCER_PATH,
    SAS_CONFIG_FULL,
    UPDATE_OPTIONS,
)

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


@dataclass
class FilterTest:
    """Class for capturing a filter test."""

    id: str
    should_pass: bool


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


async def test_setup(hass, mock_hub):
    """Test the async_setup function."""
    entry = MockConfigEntry(
        domain=azure_event_hub.DOMAIN,
        data=SAS_CONFIG_FULL,
        title="test-instance",
        options=BASIC_OPTIONS,
    )
    entry.add_to_hass(hass)
    assert await azure_event_hub.async_setup_entry(hass, entry)
    assert hass.data[azure_event_hub.DOMAIN]["hub"] is not None
    assert isinstance(hass.data[azure_event_hub.DOMAIN]["hub"], AzureEventHub)


async def test_unload_entry(hass, mock_hub):
    """Test being able to unload an entry."""
    entry = MockConfigEntry(
        domain=azure_event_hub.DOMAIN,
        data=SAS_CONFIG_FULL,
        title="test-instance",
        options=BASIC_OPTIONS,
    )
    entry.add_to_hass(hass)
    assert await azure_event_hub.async_setup_entry(hass, entry)
    assert hass.data[azure_event_hub.DOMAIN].get("hub") is not None
    assert await azure_event_hub.async_unload_entry(hass, entry)
    assert hass.data[azure_event_hub.DOMAIN].get("hub") is None


async def test_failed_test_connection(hass):
    """Test being able to unload an entry."""
    entry = MockConfigEntry(
        domain=azure_event_hub.DOMAIN,
        data=SAS_CONFIG_FULL,
        title="test-instance",
        options=BASIC_OPTIONS,
    )
    entry.add_to_hass(hass)
    with patch(
        f"{PRODUCER_PATH}.get_eventhub_properties",
        side_effect=EventHubError("test"),
    ):
        try:
            await azure_event_hub.async_setup_entry(hass, entry)
        except azure_event_hub.ConfigEntryNotReady:
            pass
        assert hass.data[azure_event_hub.DOMAIN].get("hub") is None


async def test_update_listener(hass, mock_hub):
    """Test being able to update options."""
    entry = MockConfigEntry(
        domain=azure_event_hub.DOMAIN,
        data=SAS_CONFIG_FULL,
        title="test-instance",
        options=BASIC_OPTIONS,
    )
    entry.add_to_hass(hass)
    assert await azure_event_hub.async_setup_entry(hass, entry)
    entry.options = UPDATE_OPTIONS
    await azure_event_hub.async_update_listener(hass, entry)
    assert (
        hass.data[azure_event_hub.DOMAIN]["hub"].send_interval
        == UPDATE_OPTIONS[CONF_SEND_INTERVAL]
    )


async def _setup(hass, mock_call_later, filter_config):
    """Shared set up for filtering tests."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=SAS_CONFIG_FULL,
        title="test-instance",
        options=BASIC_OPTIONS,
    )
    hass.data[DOMAIN] = {DATA_FILTER: FILTER_SCHEMA(filter_config)}
    hub = AzureEventHub(
        hass,
        azure_event_hub.client.AzureEventHubClient.from_input(**entry.data),
        hass.data[DOMAIN][DATA_FILTER],
        entry.options[CONF_SEND_INTERVAL],
        entry.options[CONF_MAX_DELAY],
    )
    entry.add_to_hass(hass)
    await hub.async_start()
    await hass.async_block_till_done()
    mock_call_later.assert_called_once()
    return mock_call_later.call_args[0][2]


async def _run_filter_tests(hass, tests, process_queue, mock_batch):
    """Run a series of filter tests on azure event hub."""
    for test in tests:
        hass.states.async_set(test.id, STATE_ON)
        await hass.async_block_till_done()
        await process_queue(None)

        if test.should_pass:
            mock_batch.add.assert_called_once()
            mock_batch.add.reset_mock()
        else:
            mock_batch.add.assert_not_called()


@pytest.fixture(name="hub")
async def setup_fixture(hass, mock_call_later):
    """Create the setup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=SAS_CONFIG_FULL,
        title="test-instance",
        options=BASIC_OPTIONS,
    )
    hass.data[DOMAIN] = {DATA_FILTER: FILTER_SCHEMA({})}
    hub = AzureEventHub(
        hass,
        azure_event_hub.client.AzureEventHubClient.from_input(**entry.data),
        hass.data[DOMAIN][DATA_FILTER],
        entry.options[CONF_SEND_INTERVAL],
        entry.options[CONF_MAX_DELAY],
    )
    entry.add_to_hass(hass)
    await hub.async_start()
    await hass.async_block_till_done()
    mock_call_later.assert_called_once()
    return hub


async def test_stop(hass, hub):
    """Test stopping the hub, which empties the queue."""
    hass.states.async_set("sensor.test", STATE_ON)
    await hass.async_block_till_done()
    assert hub._queue.qsize() == 1  # pylint: disable=protected-access
    assert await hub.async_stop()
    assert hub._queue.empty()  # pylint: disable=protected-access


async def test_send_batch_error(hass, hub):
    """Test stopping the hub, which empties the queue."""
    hass.states.async_set("sensor.test", STATE_ON)
    await hass.async_block_till_done()
    assert hub._queue.qsize() == 1  # pylint: disable=protected-access
    with patch(
        f"{PRODUCER_PATH}.send_batch", side_effect=EventHubError("test")
    ) as mock_send_batch:
        await hub.async_send(None)  # pylint: disable=protected-access
        mock_send_batch.assert_called_once()


async def test_late_event(hass, hub, mock_batch):
    """Test the on_time function."""
    with patch(
        f"{AZURE_EVENT_HUB_PATH}.utcnow",
        return_value=utcnow() + timedelta(hours=1),
    ):
        hass.states.async_set("sensor.test", STATE_ON)
        await hass.async_block_till_done()
        await hub.async_send(None)
        assert mock_batch.add.call_count == 0


async def test_full_batch(hass, hub, mock_batch):
    """Test the full batch behaviour."""
    mock_batch.add.side_effect = ValueError

    hass.states.async_set("sensor.test", STATE_ON)
    await hass.async_block_till_done()
    async with hub._client.client as client:  # pylint: disable=protected-access
        await hub.fill_batch(client)
    assert hub._queue.qsize() == 1  # pylint: disable=protected-access


async def test_allowlist(hass, mock_batch, mock_call_later):
    """Test an allowlist only config."""
    process_queue = await _setup(
        hass,
        mock_call_later,
        {
            "include_domains": ["light"],
            "include_entity_globs": ["sensor.included_*"],
            "include_entities": ["binary_sensor.included"],
        },
    )

    tests = [
        FilterTest("climate.excluded", False),
        FilterTest("light.included", True),
        FilterTest("sensor.excluded_test", False),
        FilterTest("sensor.included_test", True),
        FilterTest("binary_sensor.included", True),
        FilterTest("binary_sensor.excluded", False),
    ]

    await _run_filter_tests(hass, tests, process_queue, mock_batch)


async def test_denylist(hass, mock_batch, mock_call_later):
    """Test a denylist only config."""
    process_queue = await _setup(
        hass,
        mock_call_later,
        {
            "exclude_domains": ["climate"],
            "exclude_entity_globs": ["sensor.excluded_*"],
            "exclude_entities": ["binary_sensor.excluded"],
        },
    )

    tests = [
        FilterTest("climate.excluded", False),
        FilterTest("light.included", True),
        FilterTest("sensor.excluded_test", False),
        FilterTest("sensor.included_test", True),
        FilterTest("binary_sensor.included", True),
        FilterTest("binary_sensor.excluded", False),
    ]

    await _run_filter_tests(hass, tests, process_queue, mock_batch)


async def test_filtered_allowlist(hass, mock_batch, mock_call_later):
    """Test an allowlist config with a filtering denylist."""
    process_queue = await _setup(
        hass,
        mock_call_later,
        {
            "include_domains": ["light"],
            "include_entity_globs": ["*.included_*"],
            "exclude_domains": ["climate"],
            "exclude_entity_globs": ["*.excluded_*"],
            "exclude_entities": ["light.excluded"],
        },
    )

    tests = [
        FilterTest("light.included", True),
        FilterTest("light.excluded_test", False),
        FilterTest("light.excluded", False),
        FilterTest("sensor.included_test", True),
        FilterTest("climate.included_test", False),
    ]

    await _run_filter_tests(hass, tests, process_queue, mock_batch)


async def test_filtered_denylist(hass, mock_batch, mock_call_later):
    """Test a denylist config with a filtering allowlist."""
    process_queue = await _setup(
        hass,
        mock_call_later,
        {
            "include_entities": ["climate.included", "sensor.excluded_test"],
            "exclude_domains": ["climate"],
            "exclude_entity_globs": ["*.excluded_*"],
            "exclude_entities": ["light.excluded"],
        },
    )

    tests = [
        FilterTest("climate.excluded", False),
        FilterTest("climate.included", True),
        FilterTest("switch.excluded_test", False),
        FilterTest("sensor.excluded_test", True),
        FilterTest("light.excluded", False),
        FilterTest("light.included", True),
    ]

    await _run_filter_tests(hass, tests, process_queue, mock_batch)
