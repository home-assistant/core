"""The tests for the Vultr component."""
from copy import deepcopy
import json
from unittest.mock import patch

from homeassistant import setup
from homeassistant.components import vultr
from homeassistant.core import HomeAssistant

from .const import VALID_CONFIG

from tests.common import load_fixture


def test_setup(hass: HomeAssistant):
    """Test successful setup."""
    with patch(
        "vultr.Vultr.server_list",
        return_value=json.loads(load_fixture("server_list.json", "vultr")),
    ):
        response = vultr.setup(hass, VALID_CONFIG)
    assert response


async def test_setup_no_api_key(hass: HomeAssistant):
    """Test failed setup with missing API Key."""
    conf = deepcopy(VALID_CONFIG)
    del conf["vultr"]["api_key"]
    assert not await setup.async_setup_component(hass, vultr.DOMAIN, conf)
