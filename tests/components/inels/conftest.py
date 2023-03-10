"""Test fixtures."""
from typing import Any
from unittest.mock import Mock, patch

from inelsmqtt.const import MQTT_TRANSPORT
import pytest

from homeassistant.components import inels
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import HA_INELS_PATH

from tests.common import MockConfigEntry


@pytest.fixture
def mock_entry_setup():
    """Mock entry setup."""
    with patch(f"{HA_INELS_PATH}.async_setup_entry") as mock_setup:
        mock_setup.return_value = True
        yield mock_setup


@pytest.fixture(name="mock_mqtt")
def mock_inelsmqtt_fixture():
    """Mock inels mqtt lib."""

    def messages():
        """Return mocked messages."""
        return mqtt.mock_messages

    def discovery_all():
        """Return mocked discovered devices."""
        return mqtt.mock_discovery_all

    def subscribe(topic, qos=0, options=None, properties=None):
        """Mock subscribe fnc."""
        return mqtt.mock_messages[topic]

    def publish(topic, payload, qos=0, retain=True, properties=None):
        """Mock publish to change value of the device."""
        mqtt.mock_messages[topic] = payload

    mqtt = Mock(
        messages=messages,
        subscribe=subscribe,
        publish=publish,
        discovery_all=discovery_all,
        mock_messages=dict[str, Any](),
        mock_discovery_all=dict[str, Any](),
    )

    with patch(f"{HA_INELS_PATH}.InelsMqtt", return_value=mqtt), patch(
        f"{HA_INELS_PATH}.config_flow.InelsMqtt", return_value=mqtt
    ):
        yield mqtt


async def setup_inels_test_integration(hass: HomeAssistant):
    """Load inels integration with mocked mqtt broker."""
    hass.config.components.add(inels.DOMAIN)

    entry = MockConfigEntry(
        domain=inels.DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 1883,
            CONF_USERNAME: "test",
            CONF_PASSWORD: "pwd",
            MQTT_TRANSPORT: "tcp",
        },
        title="iNELS",
    )

    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert inels.DOMAIN in hass.config.components


async def setup_inels(hass: HomeAssistant):
    """Set up inels."""
    await setup_inels_test_integration(hass)
