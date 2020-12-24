"""The tests for the Azure Event Hub component."""
from dataclasses import dataclass

import pytest

import homeassistant.components.azure_event_hub as azure_event_hub
from homeassistant.const import STATE_ON
from homeassistant.setup import async_setup_component

from tests.async_mock import MagicMock, patch

AZURE_EVENT_HUB_PATH = "homeassistant.components.azure_event_hub"
PRODUCER_PATH = f"{AZURE_EVENT_HUB_PATH}.EventHubProducerClient"
MIN_CONFIG = {
    "event_hub_namespace": "namespace",
    "event_hub_instance_name": "name",
    "event_hub_sas_policy": "policy",
    "event_hub_sas_key": "key",
}


@dataclass
class FilterTest:
    """Class for capturing a filter test."""

    id: str
    should_pass: bool


@pytest.fixture(autouse=True, name="mock_client", scope="module")
def mock_client_fixture():
    """Mock the azure event hub producer client."""
    with patch(f"{PRODUCER_PATH}.send_batch") as mock_send_batch, patch(
        f"{PRODUCER_PATH}.close"
    ) as mock_close, patch(f"{PRODUCER_PATH}.__init__", return_value=None) as mock_init:
        yield (
            mock_init,
            mock_send_batch,
            mock_close,
        )


@pytest.fixture(autouse=True, name="mock_batch")
def mock_batch_fixture():
    """Mock batch creator and return mocked batch object."""
    mock_batch = MagicMock()
    with patch(f"{PRODUCER_PATH}.create_batch", return_value=mock_batch):
        yield mock_batch


@pytest.fixture(autouse=True, name="mock_policy")
def mock_policy_fixture():
    """Mock azure shared key credential."""
    with patch(f"{AZURE_EVENT_HUB_PATH}.EventHubSharedKeyCredential") as policy:
        yield policy


@pytest.fixture(autouse=True, name="mock_event_data")
def mock_event_data_fixture():
    """Mock the azure event data component."""
    with patch(f"{AZURE_EVENT_HUB_PATH}.EventData") as event_data:
        yield event_data


@pytest.fixture(autouse=True, name="mock_call_later")
def mock_call_later_fixture():
    """Mock async_call_later to allow queue processing on demand."""
    with patch(f"{AZURE_EVENT_HUB_PATH}.async_call_later") as mock_call_later:
        yield mock_call_later


async def test_minimal_config(hass):
    """Test the minimal config and defaults of component."""
    config = {azure_event_hub.DOMAIN: MIN_CONFIG}
    assert await async_setup_component(hass, azure_event_hub.DOMAIN, config)


async def test_full_config(hass):
    """Test the full config of component."""
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
    config[azure_event_hub.DOMAIN].update(MIN_CONFIG)
    assert await async_setup_component(hass, azure_event_hub.DOMAIN, config)


async def _setup(hass, mock_call_later, filter_config):
    """Shared set up for filtering tests."""
    config = {azure_event_hub.DOMAIN: {"filter": filter_config}}
    config[azure_event_hub.DOMAIN].update(MIN_CONFIG)

    assert await async_setup_component(hass, azure_event_hub.DOMAIN, config)
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
