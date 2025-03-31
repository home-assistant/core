"""Global fixtures for Roborock integration."""

from collections.abc import Generator
from copy import deepcopy
import pathlib
import tempfile
from typing import Any
from unittest.mock import Mock, patch

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

from .mock_data import (
    BASE_URL,
    HOME_DATA,
    MAP_DATA,
    MULTI_MAP_LIST,
    NETWORK_INFO,
    PROP,
    ROBOROCK_RRUID,
    SCENES,
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


@pytest.fixture(name="bypass_api_client_fixture")
def bypass_api_client_fixture() -> None:
    """Skip calls to the API client."""
    with (
        patch(
            "homeassistant.components.roborock.RoborockApiClient.get_home_data_v2",
            return_value=HOME_DATA,
        ),
        patch(
            "homeassistant.components.roborock.RoborockApiClient.get_scenes",
            return_value=SCENES,
        ),
        patch(
            "homeassistant.components.roborock.coordinator.RoborockLocalClientV1.load_multi_map"
        ),
    ):
        yield


@pytest.fixture(name="bypass_api_fixture")
def bypass_api_fixture(bypass_api_client_fixture: Any) -> None:
    """Skip calls to the API."""
    with (
        patch("homeassistant.components.roborock.RoborockMqttClientV1.async_connect"),
        patch("homeassistant.components.roborock.RoborockMqttClientV1._send_command"),
        patch(
            "homeassistant.components.roborock.coordinator.RoborockMqttClientV1._send_command"
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
            "homeassistant.components.roborock.coordinator.RoborockMapDataParser.parse",
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
            "homeassistant.components.roborock.coordinator.MAP_SLEEP",
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


@pytest.fixture(name="send_message_side_effect")
def send_message_side_effect_fixture() -> Any:
    """Fixture to return a side effect for the send_message method."""
    return None


@pytest.fixture(name="mock_send_message")
def mock_send_message_fixture(send_message_side_effect: Any) -> Mock:
    """Fixture to mock the send_message method."""
    with patch(
        "homeassistant.components.roborock.coordinator.RoborockLocalClientV1._send_command",
        side_effect=send_message_side_effect,
    ) as mock_send_message:
        yield mock_send_message


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


@pytest.fixture(name="config_entry_data")
def config_entry_data_fixture() -> dict[str, Any]:
    """Fixture that returns the unique id for the config entry."""
    return {
        CONF_USERNAME: USER_EMAIL,
        CONF_USER_DATA: USER_DATA.as_dict(),
        CONF_BASE_URL: BASE_URL,
    }


@pytest.fixture
def mock_roborock_entry(
    hass: HomeAssistant, config_entry_data: dict[str, Any]
) -> MockConfigEntry:
    """Create a Roborock Entry that has not been setup."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        title=USER_EMAIL,
        data=config_entry_data,
        unique_id=ROBOROCK_RRUID,
        version=1,
        minor_version=2,
    )
    mock_entry.add_to_hass(hass)
    return mock_entry


@pytest.fixture(name="platforms")
def mock_platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return []


@pytest.fixture(autouse=True)
async def mock_patforms_fixture(
    hass: HomeAssistant,
    platforms: list[Platform],
) -> Generator[None]:
    """Set up the Roborock platform."""
    with patch("homeassistant.components.roborock.PLATFORMS", platforms):
        yield


@pytest.fixture
async def setup_entry(
    hass: HomeAssistant,
    bypass_api_fixture,
    mock_roborock_entry: MockConfigEntry,
) -> Generator[MockConfigEntry]:
    """Set up the Roborock platform."""
    await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
    await hass.async_block_till_done()
    return mock_roborock_entry


@pytest.fixture(autouse=True, name="storage_path")
async def storage_path_fixture(
    hass: HomeAssistant,
) -> Generator[pathlib.Path]:
    """Test cleanup, remove any map storage persisted during the test."""
    with tempfile.TemporaryDirectory() as tmp_path:

        def get_storage_path(_: HomeAssistant, entry_id: str) -> pathlib.Path:
            return pathlib.Path(tmp_path) / entry_id

        with patch(
            "homeassistant.components.roborock.roborock_storage._storage_path_prefix",
            new=get_storage_path,
        ):
            yield pathlib.Path(tmp_path)
