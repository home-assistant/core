"""Test helper variables or methods."""
import json
from os import path
from unittest.mock import patch

from homeassistant.components.carson import DOMAIN
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture

CARSON_API_VERSION = "1.4.1"
FIXTURE_SUB_FOLDER = "carson"
CONF_AND_FORM_CREDS = {"username": "foo@bar.com", "password": "bar"}


async def setup_platform(hass, platform):
    """Set up the ring platform and prerequisites."""
    MockConfigEntry(
        domain=DOMAIN,
        data={
            "username": CONF_AND_FORM_CREDS["username"],
            "password": CONF_AND_FORM_CREDS["password"],
            "token": fixture_token(),
        },
    ).add_to_hass(hass)
    with patch("homeassistant.components.carson.PLATFORMS", [platform]):
        assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()


def carson_load_fixture(filename):
    """Return file content from Carson fixture subfolder."""
    return load_fixture(path.join(FIXTURE_SUB_FOLDER, filename))


def fixture_building_id():
    """Return Fixture Building ID from Payload."""
    return json.loads(carson_load_fixture("carson_me.json"))["data"]["properties"][0][
        "id"
    ]


def fixture_een_subdomain():
    """Return Fixture EEN Subdomain from Payload."""
    return json.loads(carson_load_fixture("carson_eagleeye_session.json"))["data"][
        "activeBrandSubdomain"
    ]


def fixture_token():
    """Return Fixture Token from Payload."""
    return json.loads(carson_load_fixture("carson_login.json"))["data"]["token"]
