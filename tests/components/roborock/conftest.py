"""Global fixtures for Roborock integration."""

import asyncio
from collections.abc import Generator
from copy import deepcopy
import logging
import pathlib
import tempfile
from typing import Any
from unittest.mock import AsyncMock, Mock, PropertyMock, patch

import pytest
from roborock import RoborockCategory
from roborock.data import (
    CombinedMapInfo,
    DyadError,
    HomeDataDevice,
    HomeDataProduct,
    NamedRoomMapping,
    NetworkInfo,
    RoborockDyadStateCode,
    ZeoError,
    ZeoState,
)
from roborock.devices.device import RoborockDevice
from roborock.devices.traits.v1.map_content import MapContent
from roborock.devices.traits.v1.volume import SoundVolume
from roborock.roborock_message import RoborockDyadDataProtocol, RoborockZeoProtocol

from homeassistant.components.roborock.const import (
    CONF_BASE_URL,
    CONF_USER_DATA,
    DOMAIN,
)
from homeassistant.const import CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from .mock_data import (
    BASE_URL,
    CLEAN_RECORD,
    CLEAN_SUMMARY,
    CONSUMABLE,
    DND_TIMER,
    HOME_DATA,
    MAP_DATA,
    MULTI_MAP_LIST,
    NETWORK_INFO_BY_DEVICE,
    ROBOROCK_RRUID,
    ROOM_MAPPING,
    SCENES,
    STATUS,
    USER_DATA,
    USER_EMAIL,
)

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


def create_dyad_trait() -> Mock:
    """Create dyad trait for A01 devices."""
    dyad_trait = AsyncMock()
    dyad_trait.query_values.return_value = {
        RoborockDyadDataProtocol.STATUS: RoborockDyadStateCode.drying.name,
        RoborockDyadDataProtocol.POWER: 100,
        RoborockDyadDataProtocol.MESH_LEFT: 111,
        RoborockDyadDataProtocol.BRUSH_LEFT: 222,
        RoborockDyadDataProtocol.ERROR: DyadError.none.name,
        RoborockDyadDataProtocol.TOTAL_RUN_TIME: 213,
    }
    return dyad_trait


def create_zeo_trait() -> Mock:
    """Create zeo trait for A01 devices."""
    zeo_trait = AsyncMock()
    zeo_trait.query_values.return_value = {
        RoborockZeoProtocol.STATE: ZeoState.drying.name,
        RoborockZeoProtocol.COUNTDOWN: 0,
        RoborockZeoProtocol.WASHING_LEFT: 253,
        RoborockZeoProtocol.ERROR: ZeoError.none.name,
    }
    return zeo_trait


@pytest.fixture(name="bypass_api_client_fixture")
def bypass_api_client_fixture() -> None:
    """Skip calls to the API client."""
    base_url_future = asyncio.Future()
    base_url_future.set_result(BASE_URL)

    with (
        patch(
            "roborock.devices.device_manager.RoborockApiClient.get_home_data_v3",
            return_value=HOME_DATA,
        ),
        patch(
            "homeassistant.components.roborock.config_flow.RoborockApiClient.base_url",
            new_callable=PropertyMock,
            return_value=base_url_future,
        ),
    ):
        yield


class FakeDevice(RoborockDevice):
    """A fake device that returns a list of devices."""

    def __init__(
        self,
        device_info: HomeDataDevice,
        product: HomeDataProduct,
    ) -> None:
        """Initialize the FakeDevice."""
        super().__init__(device_info, product, Mock(), Mock())

    async def close(self) -> None:
        """Close the device."""


class FakeDeviceManager:
    """A fake device manager that returns a list of devices."""

    def __init__(self, devices: list[RoborockDevice]) -> None:
        """Initialize the fake device manager."""
        self._devices = devices

    async def get_devices(self) -> list[RoborockDevice]:
        """Return the list of devices."""
        return self._devices


def create_v1_properties(network_info: NetworkInfo) -> Mock:
    """Create v1 properties for each fake device."""
    v1_properties = Mock()
    v1_properties.status: Any = deepcopy(STATUS)
    v1_properties.status.refresh = AsyncMock()
    v1_properties.dnd: Any = deepcopy(DND_TIMER)
    v1_properties.dnd.is_on = True
    v1_properties.dnd.refresh = AsyncMock()
    v1_properties.dnd.enable = AsyncMock()
    v1_properties.dnd.disable = AsyncMock()
    v1_properties.dnd.set_dnd_timer = AsyncMock()
    v1_properties.clean_summary: Any = deepcopy(CLEAN_SUMMARY)
    v1_properties.clean_summary.last_clean_record = deepcopy(CLEAN_RECORD)
    v1_properties.clean_summary.refresh = AsyncMock()
    v1_properties.consumables = deepcopy(CONSUMABLE)
    v1_properties.consumables.refresh = AsyncMock()
    v1_properties.consumables.reset_consumable = AsyncMock()
    v1_properties.sound_volume = SoundVolume(volume=50)
    v1_properties.sound_volume.set_volume = AsyncMock()
    v1_properties.sound_volume.refresh = AsyncMock()
    v1_properties.command = AsyncMock()
    v1_properties.command.send = AsyncMock()
    v1_properties.maps = AsyncMock()
    v1_properties.maps.current_map = MULTI_MAP_LIST.map_info[1].map_flag
    v1_properties.maps.refresh = AsyncMock()
    v1_properties.maps.set_current_map = AsyncMock()
    v1_properties.map_content = AsyncMock()
    v1_properties.map_content.image_content = b"\x89PNG-001"
    v1_properties.map_content.map_data = deepcopy(MAP_DATA)
    v1_properties.map_content.refresh = AsyncMock()
    v1_properties.child_lock = AsyncMock()
    v1_properties.child_lock.is_on = True
    v1_properties.child_lock.enable = AsyncMock()
    v1_properties.child_lock.disable = AsyncMock()
    v1_properties.child_lock.refresh = AsyncMock()
    v1_properties.led_status = AsyncMock()
    v1_properties.led_status.is_on = True
    v1_properties.led_status.enable = AsyncMock()
    v1_properties.led_status.disable = AsyncMock()
    v1_properties.led_status.refresh = AsyncMock()
    v1_properties.flow_led_status = AsyncMock()
    v1_properties.flow_led_status.is_on = True
    v1_properties.flow_led_status.enable = AsyncMock()
    v1_properties.flow_led_status.disable = AsyncMock()
    v1_properties.flow_led_status.refresh = AsyncMock()
    v1_properties.valley_electricity_timer = AsyncMock()
    v1_properties.valley_electricity_timer.is_on = True
    v1_properties.valley_electricity_timer.enable = AsyncMock()
    v1_properties.valley_electricity_timer.disable = AsyncMock()
    v1_properties.valley_electricity_timer.refresh = AsyncMock()
    v1_properties.dust_collection_mode = AsyncMock()
    v1_properties.dust_collection_mode.refresh = AsyncMock()
    v1_properties.wash_towel_mode = AsyncMock()
    v1_properties.wash_towel_mode.refresh = AsyncMock()
    v1_properties.smart_wash_params = AsyncMock()
    v1_properties.smart_wash_params.refresh = AsyncMock()
    v1_properties.home = AsyncMock()
    home_map_info = {
        map_data.map_flag: CombinedMapInfo(
            name=map_data.name,
            map_flag=map_data.map_flag,
            rooms=[
                NamedRoomMapping(
                    segment_id=ROOM_MAPPING[room.id],
                    iot_id=room.id,
                    name=room.name,
                )
                for room in HOME_DATA.rooms
            ],
        )
        for map_data in MULTI_MAP_LIST.map_info
    }
    home_map_content = {
        map_data.map_flag: MapContent(
            image_content=b"\x89PNG-001", map_data=deepcopy(MAP_DATA)
        )
        for map_data in MULTI_MAP_LIST.map_info
    }
    v1_properties.home.home_map_info = home_map_info
    v1_properties.home.current_map_data = home_map_info[STATUS.current_map]
    v1_properties.home.home_map_content = home_map_content
    v1_properties.home.refresh = AsyncMock()
    v1_properties.network_info = deepcopy(network_info)
    v1_properties.network_info.refresh = AsyncMock()
    v1_properties.routines = AsyncMock()
    v1_properties.routines.get_routines = AsyncMock(return_value=SCENES)
    v1_properties.routines.execute_routine = AsyncMock()
    # Mock diagnostics for a subset of properties
    v1_properties.as_dict.return_value = {
        "status": STATUS.as_dict(),
        "dnd": DND_TIMER.as_dict(),
    }
    return v1_properties


@pytest.fixture(name="fake_devices", autouse=True)
def fake_devices_fixture() -> list[FakeDevice]:
    """Fixture to mock the device manager."""
    devices = []
    for device_data, device_product_data in HOME_DATA.device_products.values():
        fake_device = FakeDevice(
            device_info=deepcopy(device_data),
            product=deepcopy(device_product_data),
        )
        if device_data.pv == "1.0":
            fake_device.v1_properties = create_v1_properties(
                NETWORK_INFO_BY_DEVICE[device_data.duid]
            )
        elif device_data.pv == "A01":
            if device_product_data.category == RoborockCategory.WET_DRY_VAC:
                fake_device.dyad = create_dyad_trait()
            elif device_product_data.category == RoborockCategory.WASHING_MACHINE:
                fake_device.zeo = create_zeo_trait()
            else:
                raise ValueError("Unknown A01 category in test HOME_DATA")
        else:
            raise ValueError("Unknown pv in test HOME_DATA")
        devices.append(fake_device)
    return devices


@pytest.fixture(name="fake_vacuum")
def fake_vacuum_fixture(fake_devices: list[FakeDevice]) -> FakeDevice:
    """Get the fake vacuum device."""
    return fake_devices[0]


@pytest.fixture(name="send_message_side_effect")
def send_message_side_effect_fixture() -> Any:
    """Fixture to return a side effect for the send_message method."""
    return None


@pytest.fixture(name="vacuum_command", autouse=True)
def fake_vacuum_command_fixture(
    fake_vacuum: FakeDevice, send_message_side_effect: Any
) -> Mock:
    """Get the fake vacuum device command trait for asserting that commands happened."""
    assert fake_vacuum.v1_properties is not None
    command_trait = fake_vacuum.v1_properties.command
    if send_message_side_effect is not None:
        command_trait.send.side_effect = send_message_side_effect
    return command_trait


@pytest.fixture(name="fake_create_device_manager", autouse=True)
def fake_create_device_manager_fixture(
    fake_devices: list[FakeDevice],
) -> Generator[Mock]:
    """Fixture to create a fake device manager."""
    with patch(
        "homeassistant.components.roborock.create_device_manager",
    ) as mock_create_device_manager:
        mock_create_device_manager.return_value = FakeDeviceManager(fake_devices)
        yield mock_create_device_manager


@pytest.fixture(name="bypass_device_manager", autouse=True)
def bypass_device_manager_fixture() -> None:
    """Bypass the device manager network connection."""
    with (
        patch("roborock.devices.device_manager.create_lazy_mqtt_session"),
        patch(
            "roborock.devices.device_manager.create_v1_channel"
        ) as mock_create_v1_channel,
    ):
        mock_create_v1_channel.return_value = AsyncMock()
        yield


@pytest.fixture
def bypass_api_fixture_v1_only() -> None:
    """Bypass api for tests that require only having v1 devices."""
    home_data_copy = deepcopy(HOME_DATA)
    home_data_copy.received_devices = []
    with patch(
        "roborock.devices.device_manager.RoborockApiClient.get_home_data_v3",
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
