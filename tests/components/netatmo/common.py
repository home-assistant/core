"""Common methods used across tests for Netatmo."""
import json

from tests.common import load_fixture

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
ALL_SCOPES = [
    "read_station",
    "read_camera",
    "access_camera",
    "write_camera",
    "read_presence",
    "access_presence",
    "write_presence",
    "read_homecoach",
    "read_smokedetector",
    "read_thermostat",
    "write_thermostat",
]


def fake_post_request(**args):
    """Return fake data."""
    if "url" not in args:
        return "{}"

    endpoint = args["url"].split("/")[-1]
    if endpoint in [
        "setpersonsaway",
        "setpersonshome",
        "setstate",
        "setroomthermpoint",
        "setthermmode",
        "switchhomeschedule",
    ]:
        return f'{{"{endpoint}": true}}'

    return json.loads(load_fixture(f"netatmo/{endpoint}.json"))


def fake_post_request_no_data(**args):
    """Fake error during requesting backend data."""
    return "{}"
