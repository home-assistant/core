"""Tests for the DirecTV component."""
from DirectPy import DIRECTV

from homeassistant.components.directv.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.helpers.typing import HomeAssistantType

from tests.common import MockConfigEntry

CLIENT_NAME = "Bedroom Client"
CLIENT_ADDRESS = "2CA17D1CD30X"
DEFAULT_DEVICE = "0"
HOST = "127.0.0.1"
MAIN_NAME = "Main DVR"
RECEIVER_ID = "028877455858"
SSDP_LOCATION = "http://127.0.0.1/"
UPNP_SERIAL = "RID-028877455858"

LIVE = {
    "callsign": "HASSTV",
    "date": "20181110",
    "duration": 3600,
    "isOffAir": False,
    "isPclocked": 1,
    "isPpv": False,
    "isRecording": False,
    "isVod": False,
    "major": 202,
    "minor": 65535,
    "offset": 1,
    "programId": "102454523",
    "rating": "No Rating",
    "startTime": 1541876400,
    "stationId": 3900947,
    "title": "Using Home Assistant to automate your home",
}

RECORDING = {
    "callsign": "HASSTV",
    "date": "20181110",
    "duration": 3600,
    "isOffAir": False,
    "isPclocked": 1,
    "isPpv": False,
    "isRecording": True,
    "isVod": False,
    "major": 202,
    "minor": 65535,
    "offset": 1,
    "programId": "102454523",
    "rating": "No Rating",
    "startTime": 1541876400,
    "stationId": 3900947,
    "title": "Using Home Assistant to automate your home",
    "uniqueId": "12345",
    "episodeTitle": "Configure DirecTV platform.",
}

MOCK_CONFIG = {DOMAIN: [{CONF_HOST: HOST}]}

MOCK_GET_LOCATIONS = {
    "locations": [{"locationName": MAIN_NAME, "clientAddr": DEFAULT_DEVICE}],
    "status": {
        "code": 200,
        "commandResult": 0,
        "msg": "OK.",
        "query": "/info/getLocations",
    },
}

MOCK_GET_LOCATIONS_MULTIPLE = {
    "locations": [
        {"locationName": MAIN_NAME, "clientAddr": DEFAULT_DEVICE},
        {"locationName": CLIENT_NAME, "clientAddr": CLIENT_ADDRESS},
    ],
    "status": {
        "code": 200,
        "commandResult": 0,
        "msg": "OK.",
        "query": "/info/getLocations",
    },
}

MOCK_GET_VERSION = {
    "accessCardId": "0021-1495-6572",
    "receiverId": "0288 7745 5858",
    "status": {
        "code": 200,
        "commandResult": 0,
        "msg": "OK.",
        "query": "/info/getVersion",
    },
    "stbSoftwareVersion": "0x4ed7",
    "systemTime": 1281625203,
    "version": "1.2",
}


class MockDirectvClass(DIRECTV):
    """A fake DirecTV DVR device."""

    def __init__(self, ip, port=8080, clientAddr="0", determine_state=False):
        """Initialize the fake DirecTV device."""
        super().__init__(
            ip=ip, port=port, clientAddr=clientAddr, determine_state=determine_state,
        )

        self._play = False
        self._standby = True

        if self.clientAddr == CLIENT_ADDRESS:
            self.attributes = RECORDING
            self._standby = False
        else:
            self.attributes = LIVE

    def get_locations(self):
        """Mock for get_locations method."""
        return MOCK_GET_LOCATIONS

    def get_serial_num(self):
        """Mock for get_serial_num method."""
        test_serial_num = {
            "serialNum": "9999999999",
            "status": {
                "code": 200,
                "commandResult": 0,
                "msg": "OK.",
                "query": "/info/getSerialNum",
            },
        }

        return test_serial_num

    def get_standby(self):
        """Mock for get_standby method."""
        return self._standby

    def get_tuned(self):
        """Mock for get_tuned method."""
        if self._play:
            self.attributes["offset"] = self.attributes["offset"] + 1

        test_attributes = self.attributes
        test_attributes["status"] = {
            "code": 200,
            "commandResult": 0,
            "msg": "OK.",
            "query": "/tv/getTuned",
        }
        return test_attributes

    def get_version(self):
        """Mock for get_version method."""
        return MOCK_GET_VERSION

    def key_press(self, keypress):
        """Mock for key_press method."""
        if keypress == "poweron":
            self._standby = False
            self._play = True
        elif keypress == "poweroff":
            self._standby = True
            self._play = False
        elif keypress == "play":
            self._play = True
        elif keypress == "pause" or keypress == "stop":
            self._play = False

    def tune_channel(self, source):
        """Mock for tune_channel method."""
        self.attributes["major"] = int(source)


async def setup_integration(
    hass: HomeAssistantType, skip_entry_setup: bool = False
) -> MockConfigEntry:
    """Set up the DirecTV integration in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=RECEIVER_ID, data={CONF_HOST: HOST}
    )

    entry.add_to_hass(hass)

    if not skip_entry_setup:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
