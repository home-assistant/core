"""Tests for the Hyperion component."""

from asynctest import CoroutineMock, Mock
from hyperion import const

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN

TEST_HOST = "test"
TEST_PORT = const.DEFAULT_PORT
TEST_INSTANCE = 1
TEST_ID = f"{TEST_HOST}:{TEST_PORT}-{TEST_INSTANCE}"
TEST_NAME = f"{TEST_HOST}_{TEST_PORT}_{TEST_INSTANCE}"
TEST_PRIORITY = 128
TEST_ENTITY_ID = f"{LIGHT_DOMAIN}.{TEST_NAME}"
TEST_TOKEN = "sekr1t"


def create_mock_client():
    """Create a mock Hyperion client."""
    mock_client = Mock()
    mock_client.async_client_connect = CoroutineMock(return_value=True)
    mock_client.async_client_disconnect = CoroutineMock(return_value=True)
    mock_client.async_is_auth_required = CoroutineMock(
        return_value={
            "command": "authorize-tokenRequired",
            "info": {"required": False},
            "success": True,
            "tan": 1,
        }
    )
    mock_client.adjustment = None
    mock_client.effects = None
    mock_client.id = "%s:%i-%i" % (TEST_HOST, TEST_PORT, TEST_INSTANCE)
    return mock_client
