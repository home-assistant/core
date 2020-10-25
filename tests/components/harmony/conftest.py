"""Fixtures for harmony tests."""
import pytest

from tests.async_mock import AsyncMock, MagicMock, PropertyMock

WATCH_TV_ACTIVITY_ID = 123
PLAY_MUSIC_ACTIVITY_ID = 456

ACTIVITIES_TO_IDS = {
    "Watch TV": WATCH_TV_ACTIVITY_ID,
    "Play Music": PLAY_MUSIC_ACTIVITY_ID,
}

IDS_TO_ACTIVITIES = {
    WATCH_TV_ACTIVITY_ID: "Watch TV",
    PLAY_MUSIC_ACTIVITY_ID: "Play Music",
}


class FakeHarmonyStates:
    """Class to keep track of activity states based on calls to the client mock."""

    def __init__(self, client_mock):
        """Initialize FakeHarmonyStates class."""
        self._activity_name = "Watch TV"
        self._client_mock = client_mock

    def get_activity_name(self, *args):
        """Return the current activity."""
        return self._activity_name

    def start_activity(self, *args, **kwargs):
        """Update the current activity and call the appropriate callbacks."""
        activity_id = kwargs["activity_id"]
        self._activity_name = IDS_TO_ACTIVITIES.get(activity_id)
        activity_tuple = (activity_id, self._activity_name)
        self._client_mock.callbacks.new_activity_starting(activity_tuple)
        self._client_mock.callbacks.new_activity(activity_tuple)

        return AsyncMock(return_value=(True, "unused message"))

    def get_activity_id(self, activity_name):
        """Return the mapping of an activity name to the internal id."""
        return ACTIVITIES_TO_IDS.get(activity_name)


@pytest.fixture()
def mock_harmonyclient():
    """Create a mock HarmonyClient."""
    harmonyclient_mock = MagicMock()
    stateHandler = FakeHarmonyStates(harmonyclient_mock)
    type(harmonyclient_mock).connect = AsyncMock()
    type(harmonyclient_mock).close = AsyncMock()
    type(harmonyclient_mock).get_activity_name = MagicMock(
        side_effect=stateHandler.get_activity_name
    )
    type(harmonyclient_mock).get_activity_id = stateHandler.get_activity_id
    type(harmonyclient_mock).start_activity = AsyncMock(
        side_effect=stateHandler.start_activity
    )
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
