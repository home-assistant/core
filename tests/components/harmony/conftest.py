"""Fixtures for harmony tests."""
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from aioharmony.const import ClientCallbackType
import pytest

from homeassistant.components.harmony.const import ACTIVITY_POWER_OFF

from .const import NILE_TV_ACTIVITY_ID, PLAY_MUSIC_ACTIVITY_ID, WATCH_TV_ACTIVITY_ID

ACTIVITIES_TO_IDS = {
    ACTIVITY_POWER_OFF: -1,
    "Watch TV": WATCH_TV_ACTIVITY_ID,
    "Play Music": PLAY_MUSIC_ACTIVITY_ID,
    "Nile-TV": NILE_TV_ACTIVITY_ID,
}

IDS_TO_ACTIVITIES = {
    -1: ACTIVITY_POWER_OFF,
    WATCH_TV_ACTIVITY_ID: "Watch TV",
    PLAY_MUSIC_ACTIVITY_ID: "Play Music",
    NILE_TV_ACTIVITY_ID: "Nile-TV",
}

TV_DEVICE_ID = 1234
TV_DEVICE_NAME = "My TV"

DEVICES_TO_IDS = {
    TV_DEVICE_NAME: TV_DEVICE_ID,
}

IDS_TO_DEVICES = {
    TV_DEVICE_ID: TV_DEVICE_NAME,
}


class FakeHarmonyClient:
    """FakeHarmonyClient to mock away network calls."""

    def initialize(
        self, ip_address: str = "", callbacks: ClientCallbackType = MagicMock()
    ):
        """Initialize FakeHarmonyClient class to capture callbacks."""
        self._activity_name = "Watch TV"
        self.close = AsyncMock()
        self.send_commands = AsyncMock()
        self.change_channel = AsyncMock()
        self.sync = AsyncMock()
        self._callbacks = callbacks
        self.fw_version = "123.456"

        return self

    async def connect(self):
        """Connect and call the appropriate callbacks."""
        self._callbacks.connect(None)
        return AsyncMock(return_value=(True))

    def get_activity_name(self, activity_id):
        """Return the activity name with the given activity_id."""
        return IDS_TO_ACTIVITIES.get(activity_id)

    def get_activity_id(self, activity_name):
        """Return the mapping of an activity name to the internal id."""
        return ACTIVITIES_TO_IDS.get(activity_name)

    def get_device_name(self, device_id):
        """Return the device name with the given device_id."""
        return IDS_TO_DEVICES.get(device_id)

    def get_device_id(self, device_name):
        """Return the device id with the given device_name."""
        return DEVICES_TO_IDS.get(device_name)

    async def start_activity(self, activity_id):
        """Update the current activity and call the appropriate callbacks."""
        self._activity_name = IDS_TO_ACTIVITIES.get(int(activity_id))
        activity_tuple = (activity_id, self._activity_name)
        self._callbacks.new_activity_starting(activity_tuple)
        self._callbacks.new_activity(activity_tuple)

        return AsyncMock(return_value=(True, "unused message"))

    async def power_off(self):
        """Power off all activities."""
        await self.start_activity(-1)

    @property
    def current_activity(self):
        """Return the current activity tuple."""
        return (
            self.get_activity_id(self._activity_name),
            self._activity_name,
        )

    @property
    def config(self):
        """Return the config object."""
        return self.hub_config.config

    @property
    def json_config(self):
        """Return the json config as a dict."""
        return {}

    @property
    def hub_config(self):
        """Return the client_config type."""
        config = MagicMock()
        type(config).activities = PropertyMock(
            return_value=[
                {"name": "Watch TV", "id": WATCH_TV_ACTIVITY_ID},
                {"name": "Play Music", "id": PLAY_MUSIC_ACTIVITY_ID},
                {"name": "Nile-TV", "id": NILE_TV_ACTIVITY_ID},
            ]
        )
        type(config).devices = PropertyMock(
            return_value=[{"name": TV_DEVICE_NAME, "id": TV_DEVICE_ID}]
        )
        type(config).info = PropertyMock(return_value={})
        type(config).hub_state = PropertyMock(return_value={})
        type(config).config = PropertyMock(
            return_value={
                "activity": [
                    {"id": 10000, "label": None},
                    {"id": -1, "label": "PowerOff"},
                    {"id": WATCH_TV_ACTIVITY_ID, "label": "Watch TV"},
                    {"id": PLAY_MUSIC_ACTIVITY_ID, "label": "Play Music"},
                    {"id": NILE_TV_ACTIVITY_ID, "label": "Nile-TV"},
                ]
            }
        )
        return config

    def mock_reconnection(self):
        """Simulate reconnection to the hub."""
        self._callbacks.connect(None)

    def mock_disconnection(self):
        """Simulate disconnection to the hub."""
        self._callbacks.disconnect(None)


@pytest.fixture
def harmony_client():
    """Create the FakeHarmonyClient instance."""
    return FakeHarmonyClient()


@pytest.fixture
def mock_hc(harmony_client):
    """Patch the real HarmonyClient with initialization side effect."""

    with patch(
        "homeassistant.components.harmony.data.HarmonyClient",
        side_effect=harmony_client.initialize,
    ) as fake:
        yield fake


@pytest.fixture
def mock_write_config():
    """Patches write_config_file to remove side effects."""
    with patch(
        "homeassistant.components.harmony.remote.HarmonyRemote.write_config_file",
    ) as mock:
        yield mock
