"""Define fixtures available for all tests."""

from unittest.mock import patch

import pytest
from surepy import MESTART_RESOURCE

from homeassistant.components.surepetcare.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import MOCK_API_DATA

from tests.common import MockConfigEntry


async def _mock_call(method, resource):
    if method == "GET" and resource == MESTART_RESOURCE:
        return {"data": MOCK_API_DATA}


@pytest.fixture
async def surepetcare():
    """Mock the SurePetcare for easier testing."""
    with patch("surepy.SureAPIClient", autospec=True) as mock_client_class:
        client = mock_client_class.return_value
        client.resources = {}
        client.call = _mock_call
        client.get_token.return_value = "token"
        yield client


@pytest.fixture
async def mock_config_entry_setup(hass: HomeAssistant) -> MockConfigEntry:
    """Help setting up a mocked config entry."""
    data = {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
        CONF_TOKEN: "token",
        "feeders": [12345],
        "flaps": [13579, 13576],
        "pets": [24680],
    }
    entry = MockConfigEntry(domain=DOMAIN, data=data)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    return entry
