"""Test fixtures."""

from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.core import HomeAssistant

from . import HA_INELS_PATH
from .common import DOMAIN, MockConfigEntry, get_entity, set_mock_mqtt


@pytest.fixture(name="mock_mqtt")
def mock_inelsmqtt_fixture():
    """Mock inels mqtt lib."""

    def messages():
        """Return mocked messages."""
        return mqtt.mock_messages

    def last_value(topic):
        """Mock last_value to return None if mock_last_value is empty or topic doesn't exist."""
        return mqtt.mock_last_value.get(topic) if mqtt.mock_last_value else None

    async def discovery_all():
        """Return mocked discovered devices."""
        return mqtt.mock_discovery_all

    async def subscribe(topic, qos=0, options=None, properties=None):
        """Mock subscribe fnc."""
        if isinstance(topic, list):
            return {t: mqtt.mock_messages.get(t) for t in topic}
        return mqtt.mock_messages.get(topic)

    async def publish(topic, payload, qos=0, retain=True, properties=None):
        """Mock publish to change value of the device."""
        mqtt.mock_messages[topic] = payload

    unsubscribe_topics = AsyncMock()
    unsubscribe_listeners = Mock()

    mqtt = Mock(
        messages=messages,
        subscribe=subscribe,
        publish=publish,
        last_value=last_value,
        discovery_all=discovery_all,
        unsubscribe_topics=unsubscribe_topics,
        unsubscribe_listeners=unsubscribe_listeners,
        mock_last_value=dict[str, Any](),
        mock_messages=dict[str, Any](),
        mock_discovery_all=dict[str, Any](),
    )

    with (
        patch(f"{HA_INELS_PATH}.InelsMqtt", return_value=mqtt),
    ):
        yield mqtt


@pytest.fixture
def mock_reload_entry():
    """Mock the async_reload_entry function."""
    with patch(f"{HA_INELS_PATH}.async_reload_entry") as mock_reload:
        yield mock_reload


@pytest.fixture
def setup_entity(hass: HomeAssistant, mock_mqtt):
    """Set up an entity for testing with specified configuration and status."""

    async def _setup(
        entity_config,
        status_value: bytes,
        device_available: bool = True,
        gw_available: bool = True,
        last_value=None,
        index: int | None = None,
    ):
        set_mock_mqtt(
            mock_mqtt,
            config=entity_config,
            status_value=status_value,
            gw_available=gw_available,
            device_available=device_available,
            last_value=last_value,
        )
        await setup_inels_test_integration(hass)
        return get_entity(hass, entity_config, index)

    return _setup


@pytest.fixture
def entity_config(request: pytest.FixtureRequest):
    """Fixture to provide parameterized entity configuration."""
    # This fixture will be parameterized in each test file
    return request.param


async def setup_inels_test_integration(hass: HomeAssistant):
    """Load inels integration with mocked mqtt broker."""
    hass.config.components.add(DOMAIN)

    entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        title="iNELS",
    )
    entry.add_to_hass(hass)

    with (
        patch(f"{HA_INELS_PATH}.ha_mqtt.async_wait_for_mqtt_client", return_value=True),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert DOMAIN in hass.config.components
