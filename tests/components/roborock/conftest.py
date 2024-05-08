"""Global fixtures for Roborock integration."""
from unittest.mock import patch

import pytest

from homeassistant.components.roborock.const import (
    CONF_BASE_URL,
    CONF_USER_DATA,
    DOMAIN,
)
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .mock_data import (
    BASE_URL,
    HOME_DATA,
    MAP_DATA,
    MULTI_MAP_LIST,
    NETWORK_INFO,
    PROP,
    USER_DATA,
    USER_EMAIL,
)

from tests.common import MockConfigEntry


@pytest.fixture(name="bypass_api_fixture")
def bypass_api_fixture() -> None:
    """Skip calls to the API."""
    with patch(
        "homeassistant.components.roborock.RoborockMqttClient.async_connect"
    ), patch(
        "homeassistant.components.roborock.RoborockMqttClient._send_command"
    ), patch(
        "homeassistant.components.roborock.RoborockApiClient.get_home_data",
        return_value=HOME_DATA,
    ), patch(
        "homeassistant.components.roborock.RoborockMqttClient.get_networking",
        return_value=NETWORK_INFO,
    ), patch(
        "homeassistant.components.roborock.coordinator.RoborockLocalClient.get_prop",
        return_value=PROP,
    ), patch(
        "homeassistant.components.roborock.coordinator.RoborockMqttClient.get_multi_maps_list",
        return_value=MULTI_MAP_LIST,
    ), patch(
        "homeassistant.components.roborock.coordinator.RoborockLocalClient.get_multi_maps_list",
        return_value=MULTI_MAP_LIST,
    ), patch(
        "homeassistant.components.roborock.image.RoborockMapDataParser.parse",
        return_value=MAP_DATA,
    ), patch(
        "homeassistant.components.roborock.coordinator.RoborockLocalClient.send_message"
    ), patch(
        "homeassistant.components.roborock.RoborockMqttClient._wait_response"
    ), patch(
        "homeassistant.components.roborock.coordinator.RoborockLocalClient._wait_response"
    ), patch(
        "roborock.api.AttributeCache.async_value",
    ), patch(
        "roborock.api.AttributeCache.value",
    ), patch(
        "homeassistant.components.roborock.image.MAP_SLEEP",
        0,
    ):
        yield


@pytest.fixture
def mock_roborock_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a Roborock Entry that has not been setup."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        title=USER_EMAIL,
        data={
            CONF_USERNAME: USER_EMAIL,
            CONF_USER_DATA: USER_DATA.as_dict(),
            CONF_BASE_URL: BASE_URL,
        },
    )
    mock_entry.add_to_hass(hass)
    return mock_entry


@pytest.fixture
async def setup_entry(
    hass: HomeAssistant,
    bypass_api_fixture,
    mock_roborock_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Set up the Roborock platform."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    return mock_roborock_entry
