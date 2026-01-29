"""Define fixtures available for all tests."""

from unittest.mock import patch

import pytest
from surepy.const import MESTART_RESOURCE

from homeassistant.components.surepetcare.const import (
    CONF_CREATE_PET_SELECT,
    CONF_FLAPS_MAPPINGS,
    CONF_MANUALLY_SET_LOCATION,
    CONF_PET_SELECT_OPTIONS,
    DOMAIN,
)
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import MOCK_API_DATA

from tests.common import MockConfigEntry


@pytest.fixture
async def surepetcare():
    """Mock the SurePetcare for easier testing."""
    current_response = {"data": MOCK_API_DATA}

    async def _mock_call(method, resource):
        if method == "GET" and resource == MESTART_RESOURCE:
            return current_response
        return None

    def set_call_response(response_data):
        nonlocal current_response
        current_response = response_data

    with patch("surepy.SureAPIClient", autospec=True) as mock_client_class:
        client = mock_client_class.return_value
        client.resources = {}
        client.call = _mock_call
        client.get_token.return_value = "token"
        client.set_call_response = set_call_response
        yield client


@pytest.fixture
async def mock_config_entry_setup(
    hass: HomeAssistant, request: pytest.FixtureRequest
) -> MockConfigEntry:
    """Help setting up a mocked config entry."""
    params = getattr(request, "param", {})
    with_pet_select = params.get("with_pet_select", False)

    data = {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
        CONF_TOKEN: "token",
        "feeders": [12345],
        "flaps": [13579, 13576],
        "pets": [24680],
    }

    options = {
        CONF_CREATE_PET_SELECT: False,
    }

    with_pet_select_options = {
        CONF_CREATE_PET_SELECT: True,
        CONF_MANUALLY_SET_LOCATION: {"entry": "Home", "exit": "Outside"},
        CONF_FLAPS_MAPPINGS: {
            "13579": {"entry": "Garage", "exit": "Outside"},
            "13576": {"entry": "Home", "exit": "Garage"},
        },
        CONF_PET_SELECT_OPTIONS: [
            "Garage",
            "Home",
            "Outside",
        ],
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=data,
        options=options if not with_pet_select else with_pet_select_options,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    return entry
