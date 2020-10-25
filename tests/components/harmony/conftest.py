"""Fixtures for harmony tests."""
import pytest

from tests.async_mock import AsyncMock, MagicMock, PropertyMock

WATCH_TV_ACTIVITY_ID = 123
PLAY_MUSIC_ACTIVITY_ID = 456

ACTIVITIES_TO_IDS = {
    "Watch TV": WATCH_TV_ACTIVITY_ID,
    "Play Music": PLAY_MUSIC_ACTIVITY_ID,
}

# class FakeHarmonyStates:
# def __init__(self):
# self._activity_name = "Watch TV"

# def get_activity_name(self, *args):
# return self._activity_name

# async def start_activity(self, *args, **kwargs):
# print(args)
# print(kwargs)
# fut = asyncio.Future()
# fut.return_value=True
# return await fut


@pytest.fixture()
def mock_harmonyclient():
    """Create a mock HarmonyClient."""
    # stateHandler = FakeHarmonyStates()
    harmonyclient_mock = MagicMock()
    type(harmonyclient_mock).connect = AsyncMock()
    type(harmonyclient_mock).close = AsyncMock()
    # type(harmonyclient_mock).get_activity_name = MagicMock(side_effect=stateHandler.get_activity_name)
    type(harmonyclient_mock).get_activity_name = MagicMock(return_value="Watch TV")
    type(harmonyclient_mock).get_activity_id = _get_activity_id
    # type(harmonyclient_mock).start_activity = AsyncMock(side_effect=stateHandler.start_activity, return_value=True)
    type(harmonyclient_mock).start_activity = AsyncMock()
    type(harmonyclient_mock.hub_config).activities = PropertyMock(
        return_value=[
            {"name": "Watch TV", "id": WATCH_TV_ACTIVITY_ID},
            {"name": "Play Music", "id": PLAY_MUSIC_ACTIVITY_ID},
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
                {"id": WATCH_TV_ACTIVITY_ID, "label": "Watch TV"},
                {"id": PLAY_MUSIC_ACTIVITY_ID, "label": "Play Music"},
            ]
        }
    )

    yield harmonyclient_mock


def _get_activity_id(_, activity_name):
    return ACTIVITIES_TO_IDS.get(activity_name)
