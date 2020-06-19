"""The tests for the Apache Kafka component."""
from collections import namedtuple

import pytest

import homeassistant.components.azure_event_hub as azure_event_hub
from homeassistant.core import split_entity_id
from homeassistant.helpers.entityfilter import FILTER_SCHEMA
from homeassistant.setup import async_setup_component

from tests.async_mock import AsyncMock, MagicMock, Mock, patch

AZURE_EVENT_HUB_PATH = "homeassistant.components.azure_event_hub"


@pytest.fixture(autouse=True, name="mock_client")
def mock_client_fixture():
    """Mock the azure event hub producer client."""
    with patch(f"{AZURE_EVENT_HUB_PATH}.EventHubProducerClient") as client:
        yield client


@pytest.fixture(autouse=True, name="mock_event_data")
def mock_event_data_fixture():
    """Mock the azure event data component."""
    with patch(f"{AZURE_EVENT_HUB_PATH}.EventData") as event_data:
        yield event_data


@pytest.fixture(autouse=True)
def mock_bus_and_json(hass, monkeypatch):
    """Mock the event bus listener and os component."""
    hass.async_create_task = AsyncMock()
    monkeypatch.setattr(
        f"{AZURE_EVENT_HUB_PATH}.json.dumps", Mock(return_value=MagicMock())
    )


async def test_minimal_config(hass, mock_client):
    """Test the minimal config and defaults of component."""
    config = {azure_event_hub.DOMAIN: {"event_hub_connection_string": "connection"}}
    assert await async_setup_component(hass, azure_event_hub.DOMAIN, config)


async def test_full_config(hass, mock_client):
    """Test the full config of component."""
    config = {
        azure_event_hub.DOMAIN: {
            "event_hub_connection_string": "connection",
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
    assert await async_setup_component(hass, azure_event_hub.DOMAIN, config)


FilterTest = namedtuple("FilterTest", "id should_pass")


def make_event(entity_id):
    """Make a mock event for test."""
    domain = split_entity_id(entity_id)[0]
    state = MagicMock(
        state="not blank",
        domain=domain,
        entity_id=entity_id,
        object_id="entity",
        attributes={},
    )
    return MagicMock(data={"new_state": state}, time_fired=12345)


async def _setup(hass, filter_config):
    """Shared set up for filtering tests."""
    return azure_event_hub.AzureEventHub(
        hass,
        {"event_hub_connection_string": "connection"},
        True,
        FILTER_SCHEMA(filter_config),
        5,
        30,
    )


async def test_allowlist(hass, mock_client):
    """Test an allowlist only config."""
    event_hub = await _setup(
        hass,
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

    for test in tests:
        event = make_event(test.id)
        # Azure event hub client is used asynchronously within methods, no
        # real other way to test filtering functionality
        # pylint: disable=protected-access
        assert test.should_pass == bool(event_hub._event_to_filtered_event_data(event))


async def test_denylist(hass, mock_client, loop):
    """Test a denylist only config."""
    event_hub = await _setup(
        hass,
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

    for test in tests:
        event = make_event(test.id)
        # pylint: disable=protected-access
        assert test.should_pass == bool(event_hub._event_to_filtered_event_data(event))


async def test_filtered_allowlist(hass, mock_client):
    """Test an allowlist config with a filtering denylist."""
    event_hub = await _setup(
        hass,
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

    for test in tests:
        event = make_event(test.id)
        # pylint: disable=protected-access
        assert test.should_pass == bool(event_hub._event_to_filtered_event_data(event))


async def test_filtered_denylist(hass, mock_client):
    """Test a denylist config with a filtering allowlist."""
    event_hub = await _setup(
        hass,
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

    for test in tests:
        event = make_event(test.id)
        # pylint: disable=protected-access
        assert test.should_pass == bool(event_hub._event_to_filtered_event_data(event))
