"""Test configuration for the Vultr tests."""
import json
from unittest.mock import patch

import pytest

from homeassistant.components import vultr
from homeassistant.core import HomeAssistant

from .const import VALID_CONFIG

from tests.common import load_fixture


@pytest.fixture(name="valid_config")
def valid_config(hass: HomeAssistant, requests_mock):
    """Load a valid config."""
    requests_mock.get(
        "https://api.vultr.com/v1/account/info?api_key=ABCDEFG1234567",
        text=load_fixture("account_info.json", "vultr"),
    )

    with patch(
        "vultr.Vultr.server_list",
        return_value=json.loads(load_fixture("server_list.json", "vultr")),
    ):
        # Setup hub
        vultr.setup(hass, VALID_CONFIG)

    yield
