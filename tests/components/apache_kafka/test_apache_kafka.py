"""The tests for the Apache Kafka component."""
from collections import namedtuple

import pytest

import homeassistant.components.apache_kafka as apache_kafka
from homeassistant.core import split_entity_id
from homeassistant.helpers.entityfilter import FILTER_SCHEMA
from homeassistant.setup import async_setup_component

import tests.async_mock as mock

APACHE_KAFKA_PATH = "homeassistant.components.apache_kafka"


@pytest.fixture(autouse=True, name="mock_client")
def mock_client_fixture():
    """Mock the apache kafka client."""
    with mock.patch(
        f"{APACHE_KAFKA_PATH}.AIOKafkaProducer", return_value=mock.AsyncMock()
    ) as client:
        yield client


@pytest.fixture(autouse=True)
def mock_bus_and_json(hass, monkeypatch):
    """Mock the event bus listener and os component."""
    hass.bus.async_listen = mock.MagicMock()
    monkeypatch.setattr(
        f"{APACHE_KAFKA_PATH}.json.dumps", mock.Mock(return_value=mock.MagicMock())
    )


async def test_minimal_config(hass, mock_client):
    """Test the minimal config and defaults of component."""
    config = {
        apache_kafka.DOMAIN: {
            "ip_address": "localhost",
            "port": 8080,
            "topic": "topic",
        }
    }
    assert await async_setup_component(hass, apache_kafka.DOMAIN, config)


async def test_full_config(hass, mock_client):
    """Test the full config of component."""
    config = {
        apache_kafka.DOMAIN: {
            "ip_address": "localhost",
            "port": 8080,
            "topic": "topic",
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
    assert await async_setup_component(hass, apache_kafka.DOMAIN, config)


FilterTest = namedtuple("FilterTest", "id should_pass")


def make_event(entity_id):
    """Make a mock event for test."""
    domain = split_entity_id(entity_id)[0]
    state = mock.MagicMock(
        state="not blank",
        domain=domain,
        entity_id=entity_id,
        object_id="entity",
        attributes={},
    )
    return mock.MagicMock(data={"new_state": state}, time_fired=12345)


async def _setup(hass, filter_config):
    """Shared set up for filtering tests."""
    return apache_kafka.KafkaManager(
        hass, "localhost", 8080, "topic", FILTER_SCHEMA(filter_config),
    )


async def test_allowlist(hass, mock_client):
    """Test an allowlist only config."""
    kafka = await _setup(
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
        # Since kafka client is called asynchronously, no real other way
        # to test the filtering functionality.
        # pylint: disable=protected-access
        assert test.should_pass == bool(kafka._encode_event(event))


async def test_denylist(hass, mock_client, loop):
    """Test a denylist only config."""
    kafka = await _setup(
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
        assert test.should_pass == bool(kafka._encode_event(event))


async def test_filtered_allowlist(hass, mock_client):
    """Test an allowlist config with a filtering denylist."""
    kafka = await _setup(
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
        assert test.should_pass == bool(kafka._encode_event(event))


async def test_filtered_denylist(hass, mock_client):
    """Test a denylist config with a filtering allowlist."""
    kafka = await _setup(
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
        assert test.should_pass == bool(kafka._encode_event(event))
