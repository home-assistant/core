"""The tests for the Google Pub/Sub component."""

from dataclasses import dataclass
from datetime import datetime
import os
from unittest import mock

import pytest

from homeassistant.components import google_pubsub
from homeassistant.components.google_pubsub import DateTimeJSONEncoder as victim
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

GOOGLE_PUBSUB_PATH = "homeassistant.components.google_pubsub"


@dataclass
class FilterTest:
    """Class for capturing a filter test."""

    id: str
    should_pass: bool


async def test_datetime() -> None:
    """Test datetime encoding."""
    time = datetime(2019, 1, 13, 12, 30, 5)
    assert victim().encode(time) == '"2019-01-13T12:30:05"'


async def test_no_datetime() -> None:
    """Test integer encoding."""
    assert victim().encode(42) == "42"


async def test_nested() -> None:
    """Test dictionary encoding."""
    assert victim().encode({"foo": "bar"}) == '{"foo": "bar"}'


@pytest.fixture(autouse=True, name="mock_client")
def mock_client_fixture():
    """Mock the pubsub client."""
    with mock.patch(f"{GOOGLE_PUBSUB_PATH}.PublisherClient") as client:
        setattr(
            client,
            "from_service_account_json",
            mock.MagicMock(return_value=mock.MagicMock()),
        )
        yield client


@pytest.fixture(autouse=True, name="mock_is_file")
def mock_is_file_fixture():
    """Mock os.path.isfile."""
    with mock.patch(f"{GOOGLE_PUBSUB_PATH}.os.path.isfile") as is_file:
        is_file.return_value = True
        yield is_file


@pytest.fixture(autouse=True)
def mock_json(hass, monkeypatch):
    """Mock the event bus listener and os component."""
    monkeypatch.setattr(
        f"{GOOGLE_PUBSUB_PATH}.json.dumps", mock.Mock(return_value=mock.MagicMock())
    )


async def test_minimal_config(hass: HomeAssistant, mock_client) -> None:
    """Test the minimal config and defaults of component."""
    config = {
        google_pubsub.DOMAIN: {
            "project_id": "proj",
            "topic_name": "topic",
            "credentials_json": "creds",
            "filter": {},
        }
    }
    assert await async_setup_component(hass, google_pubsub.DOMAIN, config)
    await hass.async_block_till_done()
    assert mock_client.from_service_account_json.call_count == 1
    assert mock_client.from_service_account_json.call_args[0][0] == os.path.join(
        hass.config.config_dir, "creds"
    )


async def test_full_config(hass: HomeAssistant, mock_client) -> None:
    """Test the full config of the component."""
    config = {
        google_pubsub.DOMAIN: {
            "project_id": "proj",
            "topic_name": "topic",
            "credentials_json": "creds",
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
    assert await async_setup_component(hass, google_pubsub.DOMAIN, config)
    await hass.async_block_till_done()
    assert mock_client.from_service_account_json.call_count == 1
    assert mock_client.from_service_account_json.call_args[0][0] == os.path.join(
        hass.config.config_dir, "creds"
    )


async def _setup(hass, filter_config):
    """Shared set up for filtering tests."""
    config = {
        google_pubsub.DOMAIN: {
            "project_id": "proj",
            "topic_name": "topic",
            "credentials_json": "creds",
            "filter": filter_config,
        }
    }
    assert await async_setup_component(hass, google_pubsub.DOMAIN, config)
    await hass.async_block_till_done()


async def test_allowlist(hass: HomeAssistant, mock_client) -> None:
    """Test an allowlist only config."""
    await _setup(
        hass,
        {
            "include_domains": ["light"],
            "include_entity_globs": ["sensor.included_*"],
            "include_entities": ["binary_sensor.included"],
        },
    )
    publish_client = mock_client.from_service_account_json("path")

    tests = [
        FilterTest("climate.excluded", False),
        FilterTest("light.included", True),
        FilterTest("sensor.excluded_test", False),
        FilterTest("sensor.included_test", True),
        FilterTest("binary_sensor.included", True),
        FilterTest("binary_sensor.excluded", False),
    ]

    for test in tests:
        hass.states.async_set(test.id, "not blank")
        await hass.async_block_till_done()

        was_called = publish_client.publish.call_count == 1
        assert test.should_pass == was_called
        publish_client.publish.reset_mock()


async def test_denylist(hass: HomeAssistant, mock_client) -> None:
    """Test a denylist only config."""
    await _setup(
        hass,
        {
            "exclude_domains": ["climate"],
            "exclude_entity_globs": ["sensor.excluded_*"],
            "exclude_entities": ["binary_sensor.excluded"],
        },
    )
    publish_client = mock_client.from_service_account_json("path")

    tests = [
        FilterTest("climate.excluded", False),
        FilterTest("light.included", True),
        FilterTest("sensor.excluded_test", False),
        FilterTest("sensor.included_test", True),
        FilterTest("binary_sensor.included", True),
        FilterTest("binary_sensor.excluded", False),
    ]

    for test in tests:
        hass.states.async_set(test.id, "not blank")
        await hass.async_block_till_done()

        was_called = publish_client.publish.call_count == 1
        assert test.should_pass == was_called
        publish_client.publish.reset_mock()


async def test_filtered_allowlist(hass: HomeAssistant, mock_client) -> None:
    """Test an allowlist config with a filtering denylist."""
    await _setup(
        hass,
        {
            "include_domains": ["light"],
            "include_entity_globs": ["*.included_*"],
            "exclude_domains": ["climate"],
            "exclude_entity_globs": ["*.excluded_*"],
            "exclude_entities": ["light.excluded"],
        },
    )
    publish_client = mock_client.from_service_account_json("path")

    tests = [
        FilterTest("light.included", True),
        FilterTest("light.excluded_test", False),
        FilterTest("light.excluded", False),
        FilterTest("sensor.included_test", True),
        FilterTest("climate.included_test", True),
    ]

    for test in tests:
        hass.states.async_set(test.id, "not blank")
        await hass.async_block_till_done()

        was_called = publish_client.publish.call_count == 1
        assert test.should_pass == was_called
        publish_client.publish.reset_mock()


async def test_filtered_denylist(hass: HomeAssistant, mock_client) -> None:
    """Test a denylist config with a filtering allowlist."""
    await _setup(
        hass,
        {
            "include_entities": ["climate.included", "sensor.excluded_test"],
            "exclude_domains": ["climate"],
            "exclude_entity_globs": ["*.excluded_*"],
            "exclude_entities": ["light.excluded"],
        },
    )
    publish_client = mock_client.from_service_account_json("path")

    tests = [
        FilterTest("climate.excluded", False),
        FilterTest("climate.included", True),
        FilterTest("switch.excluded_test", False),
        FilterTest("sensor.excluded_test", True),
        FilterTest("light.excluded", False),
        FilterTest("light.included", True),
    ]

    for test in tests:
        hass.states.async_set(test.id, "not blank")
        await hass.async_block_till_done()

        was_called = publish_client.publish.call_count == 1
        assert test.should_pass == was_called
        publish_client.publish.reset_mock()
