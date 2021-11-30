"""The tests for the Azure Event Hub component."""
from dataclasses import dataclass
import logging
from unittest.mock import patch

from azure.eventhub.exceptions import EventHubError
import pytest

from homeassistant.components.azure_event_hub.const import (
    CONF_MAX_DELAY,
    CONF_SEND_INTERVAL,
    DATA_FILTER,
    DOMAIN,
)
from homeassistant.components.azure_event_hub.hub import AzureEventHub
from homeassistant.const import STATE_ON
from homeassistant.helpers.entityfilter import FILTER_SCHEMA

from .const import AZURE_EVENT_HUB_PATH, BASIC_OPTIONS, PRODUCER_PATH, SAS_CONFIG_FULL

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


@dataclass
class FilterTest:
    """Class for capturing a filter test."""

    id: str
    should_pass: bool


async def _setup(hass, mock_call_later, filter_config):
    """Shared set up for filtering tests."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=SAS_CONFIG_FULL,
        title="test-instance",
        options=BASIC_OPTIONS,
    )
    hass.data[DOMAIN] = {DATA_FILTER: FILTER_SCHEMA(filter_config)}
    hub = AzureEventHub(hass, entry)
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
    hub = AzureEventHub(hass, entry)
    entry.add_to_hass(hass)
    await hub.async_start()
    await hass.async_block_till_done()
    mock_call_later.assert_called_once()
    return hub


async def test_options_update(hub):
    """Test the update options function."""
    hub.update_options({CONF_SEND_INTERVAL: 100, CONF_MAX_DELAY: 200})
    assert hub._send_interval == 100  # pylint: disable=protected-access
    assert hub._max_delay == 200  # pylint: disable=protected-access


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
        await hub._async_send(None)  # pylint: disable=protected-access
        mock_send_batch.assert_called_once()


async def test_late_event(hass, hub, mock_batch):
    """Test the on_time function."""
    with patch(
        f"{AZURE_EVENT_HUB_PATH}.hub.AzureEventHub._on_time", return_value=False
    ):
        hass.states.async_set("sensor.test", STATE_ON)
        await hass.async_block_till_done()
        await hub._async_send(None)  # pylint: disable=protected-access
        assert mock_batch.add.call_count == 0


async def test_full_batch(hass, hub, mock_batch):
    """Test the full batch behaviour."""
    mock_batch.add.side_effect = ValueError

    hass.states.async_set("sensor.test", STATE_ON)
    await hass.async_block_till_done()
    async with hub._client_config.client as client:  # pylint: disable=protected-access
        await hub._fill_batch(client)  # pylint: disable=protected-access
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
