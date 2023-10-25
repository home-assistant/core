"""Common methods used across the tests for ring devices."""
from unittest.mock import patch

from google.protobuf.json_format import Parse as JsonParse

from homeassistant.components.ring import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture

MOCK_USER_DATA = {"username": "foo", CONF_ACCESS_TOKEN: {}}


async def setup_platform(hass, platform):
    """Set up the ring platform and prerequisites."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data=MOCK_USER_DATA,
    )
    mock_config.add_to_hass(hass)
    with patch("homeassistant.components.ring.PLATFORMS", [platform]):
        assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert hass.data[DOMAIN][mock_config.entry_id]["listener_started_in_time"]
    return mock_config


def load_fixture_as_msg(filename, msg_class):
    """Load a fixture."""
    msg = msg_class()
    JsonParse(load_fixture(filename, "ring"), msg)
    return msg
