"""Fixtures for harmony tests."""
import pytest

from tests.async_mock import AsyncMock, MagicMock, PropertyMock


@pytest.fixture()
def mock_harmonyclient():
    """Create a mock HarmonyClient."""
    harmonyclient_mock = MagicMock()
    type(harmonyclient_mock).connect = AsyncMock()
    type(harmonyclient_mock).close = AsyncMock()
    type(harmonyclient_mock).get_activity_name = MagicMock(return_value="Watch TV")
    type(harmonyclient_mock.hub_config).activities = PropertyMock(
        return_value=[
            {"name": "Watch TV", "id": 123},
            {"name": "Play Music", "id": 456},
        ]
    )
    type(harmonyclient_mock.hub_config).devices = PropertyMock(
        return_value=[{"name": "My TV", "id": 1234}]
    )
    type(harmonyclient_mock.hub_config).info = PropertyMock(return_value={})
    type(harmonyclient_mock.hub_config).hub_state = PropertyMock(return_value={})
    type(harmonyclient_mock.hub_config).config = PropertyMock(
        return_value={
            "activity": [
                {"id": 123, "label": "Watch TV"},
                {"id": 456, "label": "Play Music"},
            ]
        }
    )

    yield harmonyclient_mock
