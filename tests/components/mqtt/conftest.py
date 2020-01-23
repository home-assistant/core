"""Test fixtures for mqtt component."""
import pytest

from tests.common import async_mock_mqtt_component


@pytest.fixture
def mqtt_mock(loop, hass):
    """Fixture to mock MQTT."""
    client = loop.run_until_complete(async_mock_mqtt_component(hass))
    client.reset_mock()
    return client
