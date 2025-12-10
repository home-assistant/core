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
from roborock import HomeDataRoom, MultiMapsListMapInfo, RoborockCategory
from roborock.data import (
    CombinedMapInfo,
    DnDTimer,
    DyadError,
    HomeDataDevice,
    HomeDataProduct,
    NamedRoomMapping,
    NetworkInfo,
    RoborockBase,
    RoborockDyadStateCode,
    ValleyElectricityTimer,
    ZeoError,
    ZeoState,
)
from roborock.devices.device import RoborockDevice
from roborock.devices.device_manager import DeviceManager
from roborock.devices.traits.v1 import PropertiesApi
from roborock.devices.traits.v1.clean_summary import CleanSummaryTrait
from roborock.devices.traits.v1.command import CommandTrait
from roborock.devices.traits.v1.common import V1TraitMixin
from roborock.devices.traits.v1.consumeable import ConsumableTrait
from roborock.devices.traits.v1.do_not_disturb import DoNotDisturbTrait
from roborock.devices.traits.v1.dust_collection_mode import DustCollectionModeTrait
from roborock.devices.traits.v1.home import HomeTrait
from roborock.devices.traits.v1.map_content import MapContent, MapContentTrait
from roborock.devices.traits.v1.maps import MapsTrait
from roborock.devices.traits.v1.network_info import NetworkInfoTrait
from roborock.devices.traits.v1.routines import RoutinesTrait
from roborock.devices.traits.v1.smart_wash_params import SmartWashParamsTrait
from roborock.devices.traits.v1.status import StatusTrait
from roborock.devices.traits.v1.valley_electricity_timer import (
    ValleyElectricityTimerTrait,
)
from roborock.devices.traits.v1.volume import SoundVolumeTrait
from roborock.devices.traits.v1.wash_towel_mode import WashTowelModeTrait
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
    VALLEY_ELECTRICITY_TIMER,
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
            "homeassistant.components.roborock.config_flow.RoborockApiClient.base_url",
            new_callable=PropertyMock,
            return_value=base_url_future,
        ),
    ):
        yield


class FakeDevice(RoborockDevice):
    """A fake device that returns a list of devices."""

    is_connected: bool = True
    is_local_connected: bool = True

    def __init__(
        self,
        device_info: HomeDataDevice,
        product: HomeDataProduct,
    ) -> None:
        """Initialize the FakeDevice."""
        super().__init__(device_info, product, Mock(), Mock())

    async def close(self) -> None:
        """Close the device."""


def make_mock_trait(
    trait_spec: type[V1TraitMixin] | None = None,
    dataclass_template: RoborockBase | None = None,
) -> AsyncMock:
    """Create a mock roborock trait."""
    trait = AsyncMock(spec=trait_spec or V1TraitMixin)
    if dataclass_template is not None:
        # Copy all attributes and property methods (e.g. computed properties)
        template_copy = deepcopy(dataclass_template)
        for attr_name in dir(template_copy):
            if attr_name.startswith("_"):
                continue
            setattr(trait, attr_name, getattr(template_copy, attr_name))
    trait.refresh = AsyncMock()
    return trait


def make_mock_switch(
    trait_spec: type[V1TraitMixin] | None = None,
    dataclass_template: RoborockBase | None = None,
) -> AsyncMock:
    """Create a mock roborock switch trait."""
    trait = make_mock_trait(
        trait_spec=trait_spec,
        dataclass_template=dataclass_template,
    )
    trait.is_on = True
    trait.enable = AsyncMock()
    trait.enable.side_effect = lambda: setattr(trait, "is_on", True)
    trait.disable = AsyncMock()
    trait.disable.side_effect = lambda: setattr(trait, "is_on", False)
    return trait


def make_dnd_timer(dataclass_template: RoborockBase) -> AsyncMock:
    """Make a function for the fake timer trait that emulates the real behavior."""
    dnd_trait = make_mock_switch(
        trait_spec=DoNotDisturbTrait,
        dataclass_template=dataclass_template,
    )

    async def set_dnd_timer(timer: DnDTimer) -> None:
        setattr(dnd_trait, "start_hour", timer.start_hour)
        setattr(dnd_trait, "start_minute", timer.start_minute)
        setattr(dnd_trait, "end_hour", timer.end_hour)
        setattr(dnd_trait, "end_minute", timer.end_minute)
        setattr(dnd_trait, "enabled", timer.enabled)

    dnd_trait.set_dnd_timer = AsyncMock()
    dnd_trait.set_dnd_timer.side_effect = set_dnd_timer
    return dnd_trait


def make_valley_electric_timer(dataclass_template: RoborockBase) -> AsyncMock:
    """Make a function for the fake timer trait that emulates the real behavior."""
    valley_electric_timer_trait = make_mock_switch(
        trait_spec=ValleyElectricityTimerTrait,
        dataclass_template=dataclass_template,
    )

    async def set_timer(timer: ValleyElectricityTimer) -> None:
        setattr(valley_electric_timer_trait, "start_hour", timer.start_hour)
        setattr(valley_electric_timer_trait, "start_minute", timer.start_minute)
        setattr(valley_electric_timer_trait, "end_hour", timer.end_hour)
        setattr(valley_electric_timer_trait, "end_minute", timer.end_minute)
        setattr(valley_electric_timer_trait, "enabled", timer.enabled)

    valley_electric_timer_trait.set_timer = AsyncMock()
    valley_electric_timer_trait.set_timer.side_effect = set_timer
    return valley_electric_timer_trait


def make_home_trait(
    map_info: list[MultiMapsListMapInfo],
    current_map: int | None,
    room_mapping: dict[int, int],
    rooms: list[HomeDataRoom],
) -> AsyncMock:
    """Create a mock roborock home trait."""
    home_trait = make_mock_trait(trait_spec=HomeTrait)
    home_map_info = {
        map_data.map_flag: CombinedMapInfo(
            name=map_data.name,
            map_flag=map_data.map_flag,
            rooms=[
                NamedRoomMapping(
                    segment_id=room_mapping[room.id],
                    iot_id=room.id,
                    name=room.name,
                )
                for room in rooms
            ],
        )
        for map_data in map_info
    }
    home_map_content = {
        map_data.map_flag: MapContent(
            image_content=b"\x89PNG-001", map_data=deepcopy(MAP_DATA)
        )
        for map_data in map_info
    }
    home_trait.home_map_info = home_map_info
    home_trait.current_map_data = home_map_info[current_map]
    home_trait.home_map_content = home_map_content
    return home_trait


def create_v1_properties(network_info: NetworkInfo) -> AsyncMock:
    """Create v1 properties for each fake device."""
    v1_properties = AsyncMock(spec=PropertiesApi)
    v1_properties.status = make_mock_trait(
        trait_spec=StatusTrait,
        dataclass_template=STATUS,
    )
    v1_properties.dnd = make_dnd_timer(dataclass_template=DND_TIMER)
    v1_properties.clean_summary = make_mock_trait(
        trait_spec=CleanSummaryTrait,
        dataclass_template=CLEAN_SUMMARY,
    )
    v1_properties.clean_summary.last_clean_record = deepcopy(CLEAN_RECORD)
    v1_properties.consumables = make_mock_trait(
        trait_spec=ConsumableTrait, dataclass_template=CONSUMABLE
    )
    v1_properties.consumables.reset_consumable = AsyncMock()
    v1_properties.sound_volume = make_mock_trait(trait_spec=SoundVolumeTrait)
    v1_properties.sound_volume.volume = 50
    v1_properties.sound_volume.set_volume = AsyncMock()
    v1_properties.sound_volume.set_volume.side_effect = lambda vol: setattr(
        v1_properties.sound_volume, "volume", vol
    )
    v1_properties.command = AsyncMock(spec=CommandTrait)
    v1_properties.command.send = AsyncMock()
    v1_properties.maps = make_mock_trait(trait_spec=MapsTrait)
    v1_properties.maps.current_map = MULTI_MAP_LIST.map_info[1].map_flag
    v1_properties.maps.set_current_map = AsyncMock()
    v1_properties.map_content = make_mock_trait(trait_spec=MapContentTrait)
    v1_properties.map_content.image_content = b"\x89PNG-001"
    v1_properties.map_content.map_data = deepcopy(MAP_DATA)
    v1_properties.child_lock = make_mock_switch()
    v1_properties.led_status = make_mock_switch()
    v1_properties.flow_led_status = make_mock_switch()
    v1_properties.valley_electricity_timer = make_valley_electric_timer(
        dataclass_template=VALLEY_ELECTRICITY_TIMER,
    )
    v1_properties.dust_collection_mode = make_mock_trait(
        trait_spec=DustCollectionModeTrait
    )
    v1_properties.wash_towel_mode = make_mock_trait(trait_spec=WashTowelModeTrait)
    v1_properties.smart_wash_params = make_mock_trait(trait_spec=SmartWashParamsTrait)
    v1_properties.home = make_home_trait(
        map_info=MULTI_MAP_LIST.map_info,
        current_map=STATUS.current_map,
        room_mapping=ROOM_MAPPING,
        rooms=HOME_DATA.rooms,
    )
    v1_properties.network_info = make_mock_trait(
        trait_spec=NetworkInfoTrait,
        dataclass_template=network_info,
    )
    v1_properties.routines = make_mock_trait(trait_spec=RoutinesTrait)
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
        fake_device.is_connected = True
        fake_device.is_local_connected = True
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


@pytest.fixture(name="send_message_exception")
def send_message_exception_fixture() -> Exception | None:
    """Fixture to return a side effect for the send_message method."""
    return None


@pytest.fixture(name="vacuum_command", autouse=True)
def fake_vacuum_command_fixture(
    fake_vacuum: FakeDevice,
    send_message_exception: Exception | None,
) -> AsyncMock:
    """Get the fake vacuum device command trait for asserting that commands happened."""
    assert fake_vacuum.v1_properties is not None
    command_trait = fake_vacuum.v1_properties.command
    if send_message_exception is not None:
        command_trait.send.side_effect = send_message_exception
    return command_trait


@pytest.fixture(name="device_manager")
def device_manager_fixture(
    fake_devices: list[FakeDevice],
) -> AsyncMock:
    """Fixture to create a fake device manager."""
    device_manager = AsyncMock(spec=DeviceManager)
    device_manager.get_devices = AsyncMock(return_value=fake_devices)
    return device_manager


@pytest.fixture(name="fake_create_device_manager", autouse=True)
def fake_create_device_manager_fixture(
    device_manager: AsyncMock,
) -> None:
    """Fixture to create a fake device manager."""
    with patch(
        "homeassistant.components.roborock.create_device_manager",
    ) as mock_create_device_manager:
        mock_create_device_manager.return_value = device_manager
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
