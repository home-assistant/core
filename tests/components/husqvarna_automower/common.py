"""Tessie common helpers for tests."""
from unittest.mock import patch

from aioautomower.model import MowerAttributes, MowerList

from homeassistant.components.husqvarna_automower.const import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from tests.common import MockConfigEntry, load_fixture

# from tests.components.husqvarna_automower.conftest import mower_list_fixture
TEST_MOWER_ID = "c7233734-b219-4287-a173-08e3643f89f0"
USER_ID = "123"

TEST_TOKEN = load_fixture("jwt", DOMAIN)
TEST_MOWERLIST = {
    "data": [
        {
            "type": "mower",
            "id": "c7233734-b219-4287-a173-08e3643f89f0",
            "attributes": {
                "system": {
                    "name": "Test Mower 1",
                    "model": "450XH-TEST",
                    "serialNumber": 123,
                },
                "battery": {"batteryPercent": 100},
                "capabilities": {
                    "headlights": True,
                    "workAreas": False,
                    "position": True,
                    "stayOutZones": False,
                },
                "mower": {
                    "mode": "MAIN_AREA",
                    "activity": "PARKED_IN_CS",
                    "state": "RESTRICTED",
                    "errorCode": 0,
                    "errorCodeTimestamp": 0,
                },
                "calendar": {
                    "tasks": [
                        {
                            "start": 1140,
                            "duration": 300,
                            "monday": True,
                            "tuesday": False,
                            "wednesday": True,
                            "thursday": False,
                            "friday": True,
                            "saturday": False,
                            "sunday": False,
                        },
                        {
                            "start": 0,
                            "duration": 480,
                            "monday": False,
                            "tuesday": True,
                            "wednesday": False,
                            "thursday": True,
                            "friday": False,
                            "saturday": True,
                            "sunday": False,
                        },
                    ]
                },
                "planner": {
                    "nextStartTimestamp": 1685991600000,
                    "override": {"action": "NOT_ACTIVE"},
                    "restrictedReason": "WEEK_SCHEDULE",
                },
                "metadata": {"connected": True, "statusTimestamp": 1697669932683},
                "positions": [
                    {"latitude": 35.5402913, "longitude": -82.5527055},
                    {"latitude": 35.5407693, "longitude": -82.5521503},
                    {"latitude": 35.5403241, "longitude": -82.5522924},
                    {"latitude": 35.5406973, "longitude": -82.5518579},
                    {"latitude": 35.5404659, "longitude": -82.5516567},
                    {"latitude": 35.5406318, "longitude": -82.5515709},
                    {"latitude": 35.5402477, "longitude": -82.5519437},
                    {"latitude": 35.5403503, "longitude": -82.5516889},
                    {"latitude": 35.5401429, "longitude": -82.551536},
                    {"latitude": 35.5405489, "longitude": -82.5512195},
                    {"latitude": 35.5404005, "longitude": -82.5512115},
                    {"latitude": 35.5405969, "longitude": -82.551418},
                    {"latitude": 35.5403437, "longitude": -82.5523917},
                    {"latitude": 35.5403481, "longitude": -82.5520054},
                ],
                "cuttingHeight": 4,
                "headlight": {"mode": "EVENING_ONLY"},
                "statistics": {
                    "numberOfChargingCycles": 1380,
                    "numberOfCollisions": 11396,
                    "totalChargingTime": 4334400,
                    "totalCuttingTime": 4194000,
                    "totalDriveDistance": 1780272,
                    "totalRunningTime": 4564800,
                    "totalSearchingTime": 370800,
                },
            },
        }
    ]
}


# TEST_VEHICLE_STATE_ONLINE = load_json_object_fixture("online.json", DOMAIN)
# TEST_VEHICLE_STATE_ASLEEP = load_json_object_fixture("asleep.json", DOMAIN)
# TEST_RESPONSE = {"result": True}
# TEST_RESPONSE_ERROR = {"result": False, "reason": "reason why"}
TEST_CONFIG = {CONF_ACCESS_TOKEN: "1234567890"}
# TEST_CONFIG = {CONF_ACCESS_TOKEN: "1234567890"}
# TESSIE_URL = "https://api.tessie.com/"

# TEST_REQUEST_INFO = RequestInfo(
#     url=TESSIE_URL, method="GET", headers={}, real_url=TESSIE_URL
# )

# ERROR_AUTH = ClientResponseError(
#     request_info=TEST_REQUEST_INFO, history=None, status=HTTPStatus.UNAUTHORIZED
# )
# ERROR_TIMEOUT = ClientResponseError(
#     request_info=TEST_REQUEST_INFO, history=None, status=HTTPStatus.REQUEST_TIMEOUT
# )
# ERROR_UNKNOWN = ClientResponseError(
#     request_info=TEST_REQUEST_INFO, history=None, status=HTTPStatus.BAD_REQUEST
# )
# ERROR_VIRTUAL_KEY = ClientResponseError(
#     request_info=TEST_REQUEST_INFO,
#     history=None,
#     status=HTTPStatus.INTERNAL_SERVER_ERROR,
# )
# ERROR_CONNECTION = ClientConnectionError()


async def setup_platform(hass: HomeAssistant, side_effect=None):
    """Set up the Tessie platform."""

    mowers_list = MowerList(**TEST_MOWERLIST)
    mowers = {}
    for mower in mowers_list.data:
        mowers[mower.id] = mower.attributes
    test_data = mowers

    config_entry_oauth2_flow.async_register_implementation(
        hass,
        DOMAIN,
        config_entry_oauth2_flow.LocalOAuth2Implementation(
            hass,
            DOMAIN,
            "awfwf",
            "afwfe",
            "http://example/authorize",
            "http://example/token",
        ),
    )

    mock_entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Husqvarna Automower of Erika Mustermann",
        data={
            "auth_implementation": "husqvarna_automower",
            "token": {
                "access_token": TEST_TOKEN,
                "scope": "iam:read amc:api",
                "expires_in": 86399,
                "refresh_token": "3012bc9f-7a65-4240-b817-9154ffdcc30f",
                "provider": "husqvarna",
                "user_id": USER_ID,
                "token_type": "Bearer",
                "expires_at": 1000000000000,
            },
        },
        unique_id=USER_ID,
        entry_id="automower_test",
    )
    mock_entry.add_to_hass(hass)
    mower_data: MowerAttributes = test_data
    with patch(
        "homeassistant.components.husqvarna_automower.coordinator.AutomowerDataUpdateCoordinator._async_update_data",
        return_value=mower_data,
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    return mock_entry
