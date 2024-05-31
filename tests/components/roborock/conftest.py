"""Global fixtures for Roborock integration."""

from unittest.mock import patch

import pytest
from roborock import RoomMapping

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
    with (
        patch("homeassistant.components.roborock.RoborockMqttClientV1.async_connect"),
        patch("homeassistant.components.roborock.RoborockMqttClientV1._send_command"),
        patch(
            "homeassistant.components.roborock.RoborockApiClient.get_home_data",
            return_value=HOME_DATA,
        ),
        patch(
            "homeassistant.components.roborock.RoborockMqttClientV1.get_networking",
            return_value=NETWORK_INFO,
        ),
        patch(
            "homeassistant.components.roborock.coordinator.RoborockLocalClientV1.get_prop",
            return_value=PROP,
        ),
        patch(
            "homeassistant.components.roborock.coordinator.RoborockMqttClientV1.get_multi_maps_list",
            return_value=MULTI_MAP_LIST,
        ),
        patch(
            "homeassistant.components.roborock.coordinator.RoborockLocalClientV1.get_multi_maps_list",
            return_value=MULTI_MAP_LIST,
        ),
        patch(
            "homeassistant.components.roborock.image.RoborockMapDataParser.parse",
            return_value=MAP_DATA,
        ),
        patch(
            "homeassistant.components.roborock.coordinator.RoborockLocalClientV1.send_message"
        ),
        patch("homeassistant.components.roborock.RoborockMqttClientV1._wait_response"),
        patch(
            "homeassistant.components.roborock.coordinator.RoborockLocalClientV1._wait_response"
        ),
        patch(
            "roborock.version_1_apis.AttributeCache.async_value",
        ),
        patch(
            "roborock.version_1_apis.AttributeCache.value",
        ),
        patch(
            "homeassistant.components.roborock.image.MAP_SLEEP",
            0,
        ),
        patch(
            "homeassistant.components.roborock.coordinator.RoborockLocalClientV1.get_room_mapping",
            return_value=[
                RoomMapping(16, "2362048"),
                RoomMapping(17, "2362044"),
                RoomMapping(18, "2362041"),
            ],
        ),
        patch(
            "homeassistant.components.roborock.coordinator.RoborockMqttClientV1.get_room_mapping",
            return_value=[
                RoomMapping(16, "2362048"),
                RoomMapping(17, "2362044"),
                RoomMapping(18, "2362041"),
            ],
        ),
        patch(
            "homeassistant.components.roborock.coordinator.RoborockMqttClientV1.get_map_v1",
            return_value=b"123",
        ),
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
