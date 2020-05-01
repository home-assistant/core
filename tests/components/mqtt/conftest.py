"""Test fixtures for mqtt component."""
import pytest

from tests.common import async_mock_mqtt_component


@pytest.fixture
def mqtt_mock(loop, hass):
    """Fixture to mock MQTT."""
    client = loop.run_until_complete(async_mock_mqtt_component(hass))
    client.reset_mock()
    return client


@pytest.fixture(autouse=True)
def fail_on_log_exception(request, monkeypatch):
    """Fixture to fail if MQTT callbacks throw."""
    if "no_fail_on_log_exception" in request.keywords:
        return

    def log_exception(format_err, *args):
        pytest.fail()

    monkeypatch.setattr("homeassistant.util.logging.log_exception", log_exception)
