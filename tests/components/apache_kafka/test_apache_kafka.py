"""The tests for the Apache Kafka component."""
from collections import namedtuple

import pytest

import homeassistant.components.apache_kafka as apache_kafka
from homeassistant.const import STATE_ON
from homeassistant.core import split_entity_id
from homeassistant.setup import async_setup_component

from tests.async_mock import MagicMock, patch

APACHE_KAFKA_PATH = "homeassistant.components.apache_kafka"
PRODUCER_PATH = f"{APACHE_KAFKA_PATH}.AIOKafkaProducer"
MIN_CONFIG = {
    "ip_address": "localhost",
    "port": 8080,
    "topic": "topic",
}
FilterTest = namedtuple("FilterTest", "id should_pass")
MockKafkaClient = namedtuple("MockKafkaClient", "init start send_and_wait")


@pytest.fixture(name="mock_client")
def mock_client_fixture():
    """Mock the apache kafka client."""
    with patch(f"{PRODUCER_PATH}.start") as start:
        with patch(f"{PRODUCER_PATH}.send_and_wait") as send_and_wait:
            with patch(f"{PRODUCER_PATH}.__init__", return_value=None) as init:
                yield MockKafkaClient(init, start, send_and_wait)


@pytest.fixture(autouse=True, scope="module")
def mock_client_stop():
    """Mock client stop at module scope for teardown."""
    with patch(f"{PRODUCER_PATH}.stop") as stop:
        yield stop


async def test_minimal_config(hass, mock_client):
    """Test the minimal config and defaults of component."""
    config = {apache_kafka.DOMAIN: MIN_CONFIG}
    assert await async_setup_component(hass, apache_kafka.DOMAIN, config)
    await hass.async_block_till_done()
    assert mock_client.start.called_once


async def test_full_config(hass, mock_client):
    """Test the full config of component."""
    config = {
        apache_kafka.DOMAIN: {
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
    config[apache_kafka.DOMAIN].update(MIN_CONFIG)

    assert await async_setup_component(hass, apache_kafka.DOMAIN, config)
    await hass.async_block_till_done()
    assert mock_client.start.called_once


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


async def _setup(hass, mock_client, filter_config):
    """Shared set up for filtering tests."""
    config = {apache_kafka.DOMAIN: {"filter": filter_config}}
    config[apache_kafka.DOMAIN].update(MIN_CONFIG)

    assert await async_setup_component(hass, apache_kafka.DOMAIN, config)
    await hass.async_block_till_done()


async def test_allowlist(hass, mock_client):
    """Test an allowlist only config."""
    await _setup(
        hass,
        mock_client,
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
        hass.states.async_set(test.id, STATE_ON)
        await hass.async_block_till_done()

        if test.should_pass:
            mock_client.send_and_wait.assert_called_once()
            mock_client.send_and_wait.reset_mock()
        else:
            mock_client.send_and_wait.assert_not_called()


async def test_denylist(hass, mock_client):
    """Test a denylist only config."""
    await _setup(
        hass,
        mock_client,
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
        hass.states.async_set(test.id, STATE_ON)
        await hass.async_block_till_done()

        if test.should_pass:
            mock_client.send_and_wait.assert_called_once()
            mock_client.send_and_wait.reset_mock()
        else:
            mock_client.send_and_wait.assert_not_called()


async def test_filtered_allowlist(hass, mock_client):
    """Test an allowlist config with a filtering denylist."""
    await _setup(
        hass,
        mock_client,
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
        hass.states.async_set(test.id, STATE_ON)
        await hass.async_block_till_done()

        if test.should_pass:
            mock_client.send_and_wait.assert_called_once()
            mock_client.send_and_wait.reset_mock()
        else:
            mock_client.send_and_wait.assert_not_called()


async def test_filtered_denylist(hass, mock_client):
    """Test a denylist config with a filtering allowlist."""
    await _setup(
        hass,
        mock_client,
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
        hass.states.async_set(test.id, STATE_ON)
        await hass.async_block_till_done()

        if test.should_pass:
            mock_client.send_and_wait.assert_called_once()
            mock_client.send_and_wait.reset_mock()
        else:
            mock_client.send_and_wait.assert_not_called()
