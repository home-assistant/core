"""Test Onkyo helpers."""
import asyncio

from homeassistant.components.onkyo.helpers import async_discover_connections

from tests.common import AsyncMock, Mock, patch

TEST_NAME_1 = "OnkyoReceiver"
TEST_HOST_1 = "192.168.1.2"


def get_mock_connection(host, name):
    """Return a mock connection."""
    mock_connection = Mock()
    mock_connection.name = name
    mock_connection.host = host

    mock_connection.connect = AsyncMock()
    mock_connection.close = Mock()

    return mock_connection


async def test_discover_single_connection(hass):
    """Test if a discovered connection is returned correct."""
    mock_connection = get_mock_connection(TEST_HOST_1, TEST_NAME_1)

    with patch(
        "pyeiscp.Connection.discover",
        side_effect=lambda host, discovery_callback, timeout: asyncio.ensure_future(
            discovery_callback(mock_connection)
        ),
    ):
        result = await async_discover_connections(host=TEST_HOST_1)

    assert len(result) == 1
    assert result[0] == mock_connection

    assert len(mock_connection.connect.mock_calls) == 0
    assert len(mock_connection.close.mock_calls) == 0
