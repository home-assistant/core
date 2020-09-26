"""Tests for the Hyperion component."""

from asynctest import CoroutineMock, Mock
from hyperion import const

from homeassistant.components.light import DOMAIN

TEST_HOST = "test-hyperion-host"
TEST_PORT = const.DEFAULT_PORT
TEST_NAME = "test_hyperion_name"
TEST_INSTANCE = 1
TEST_PRIORITY = 128
TEST_ENTITY_ID = f"{DOMAIN}.{TEST_NAME}"


def create_mock_client():
    """Create a mock Hyperion client."""
    mock_client = Mock()
    mock_client.async_client_connect = CoroutineMock(return_value=True)
    mock_client.async_client_disconnect = CoroutineMock(return_value=True)
    mock_client.adjustment = None
    mock_client.effects = None
    mock_client.id = "%s:%i-%i" % (TEST_HOST, TEST_PORT, TEST_INSTANCE)
    return mock_client
