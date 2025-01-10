"""Global fixtures for Roborock integration."""

from collections.abc import Generator
from copy import deepcopy
from unittest.mock import patch

import pytest
from roborock import RoborockCategory, RoomMapping
from roborock.code_mappings import DyadError, RoborockDyadStateCode, ZeoError, ZeoState
from roborock.roborock_message import RoborockDyadDataProtocol, RoborockZeoProtocol
from roborock.version_a01_apis import RoborockMqttClientA01

from homeassistant.components.roborock.const import (
    CONF_BASE_URL,
    CONF_USER_DATA,
    DOMAIN,
)
from homeassistant.const import CONF_USERNAME, Platform
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


class A01Mock(RoborockMqttClientA01):
    """A class to mock the A01 client."""

    def __init__(self, user_data, device_info, category) -> None:
        """Initialize the A01Mock."""
        super().__init__(user_data, device_info, category)
        if category == RoborockCategory.WET_DRY_VAC:
            self.protocol_responses = {
                RoborockDyadDataProtocol.STATUS: RoborockDyadStateCode.drying.name,
                RoborockDyadDataProtocol.POWER: 100,
                RoborockDyadDataProtocol.MESH_LEFT: 111,
                RoborockDyadDataProtocol.BRUSH_LEFT: 222,
                RoborockDyadDataProtocol.ERROR: DyadError.none.name,
                RoborockDyadDataProtocol.TOTAL_RUN_TIME: 213,
            }
        elif category == RoborockCategory.WASHING_MACHINE:
            self.protocol_responses: list[RoborockZeoProtocol] = {
                RoborockZeoProtocol.STATE: ZeoState.drying.name,
                RoborockZeoProtocol.COUNTDOWN: 0,
                RoborockZeoProtocol.WASHING_LEFT: 253,
                RoborockZeoProtocol.ERROR: ZeoError.none.name,
            }

    async def update_values(
        self, dyad_data_protocols: list[RoborockDyadDataProtocol | RoborockZeoProtocol]
    ):
        """Update values with a predetermined response that can be overridden."""
        return {prot: self.protocol_responses[prot] for prot in dyad_data_protocols}


@pytest.fixture(name="bypass_api_fixture")
def bypass_api_fixture() -> None:
    """Skip calls to the API."""
    with (
        patch("homeassistant.components.roborock.RoborockMqttClientV1.async_connect"),
        patch("homeassistant.components.roborock.RoborockMqttClientV1._send_command"),
        patch(
            "homeassistant.components.roborock.RoborockApiClient.get_home_data_v2",
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
        patch(
            "homeassistant.components.roborock.coordinator.RoborockClientA01",
            A01Mock,
        ),
        patch("homeassistant.components.roborock.RoborockMqttClientA01", A01Mock),
    ):
        yield


@pytest.fixture
def bypass_api_fixture_v1_only(bypass_api_fixture) -> None:
    """Bypass api for tests that require only having v1 devices."""
    home_data_copy = deepcopy(HOME_DATA)
    home_data_copy.received_devices = []
    with patch(
        "homeassistant.components.roborock.RoborockApiClient.get_home_data_v2",
        return_value=home_data_copy,
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
        unique_id=USER_EMAIL,
    )
    mock_entry.add_to_hass(hass)
    return mock_entry


@pytest.fixture(name="platforms")
def mock_platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return []


@pytest.fixture
async def setup_entry(
    hass: HomeAssistant,
    bypass_api_fixture,
    mock_roborock_entry: MockConfigEntry,
    platforms: list[Platform],
) -> Generator[MockConfigEntry]:
    """Set up the Roborock platform."""
    with patch("homeassistant.components.roborock.PLATFORMS", platforms):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
        yield mock_roborock_entry
