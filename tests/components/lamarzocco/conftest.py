"""Lamarzocco session fixtures."""

from collections.abc import Generator
import json
from unittest.mock import MagicMock, patch

from bleak.backends.device import BLEDevice
from lmcloud.const import FirmwareType, MachineModel, SteamLevel
from lmcloud.lm_machine import LaMarzoccoMachine
from lmcloud.models import LaMarzoccoDeviceInfo
import pytest

from homeassistant.components.lamarzocco.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_MODEL, CONF_NAME, CONF_TOKEN
from homeassistant.core import HomeAssistant

from . import SERIAL_DICT, USER_INPUT, async_init_integration

from tests.common import MockConfigEntry, load_fixture, load_json_object_fixture


@pytest.fixture
def mock_config_entry(
    hass: HomeAssistant, mock_lamarzocco: MagicMock
) -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="My LaMarzocco",
        domain=DOMAIN,
        version=2,
        data=USER_INPUT
        | {
            CONF_MODEL: mock_lamarzocco.model,
            CONF_HOST: "host",
            CONF_TOKEN: "token",
            CONF_NAME: "GS3",
        },
        unique_id=mock_lamarzocco.serial_number,
    )


@pytest.fixture
def mock_config_entry_no_local_connection(
    hass: HomeAssistant, mock_lamarzocco: MagicMock
) -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="My LaMarzocco",
        domain=DOMAIN,
        version=2,
        data=USER_INPUT
        | {
            CONF_MODEL: mock_lamarzocco.model,
            CONF_TOKEN: "token",
            CONF_NAME: "GS3",
        },
        unique_id=mock_lamarzocco.serial_number,
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_lamarzocco: MagicMock
) -> MockConfigEntry:
    """Set up the La Marzocco integration for testing."""
    await async_init_integration(hass, mock_config_entry)

    return mock_config_entry


@pytest.fixture
def device_fixture() -> MachineModel:
    """Return the device fixture for a specific device."""
    return MachineModel.GS3_AV


@pytest.fixture
def mock_device_info() -> LaMarzoccoDeviceInfo:
    """Return a mocked La Marzocco device info."""
    return LaMarzoccoDeviceInfo(
        model=MachineModel.GS3_AV,
        serial_number="GS01234",
        name="GS3",
        communication_key="token",
    )


@pytest.fixture
def mock_cloud_client(
    mock_device_info: LaMarzoccoDeviceInfo,
) -> Generator[MagicMock]:
    """Return a mocked LM cloud client."""
    with (
        patch(
            "homeassistant.components.lamarzocco.config_flow.LaMarzoccoCloudClient",
            autospec=True,
        ) as cloud_client,
        patch(
            "homeassistant.components.lamarzocco.LaMarzoccoCloudClient",
            new=cloud_client,
        ),
    ):
        client = cloud_client.return_value
        client.get_customer_fleet.return_value = {
            mock_device_info.serial_number: mock_device_info
        }
        yield client


@pytest.fixture
def mock_lamarzocco(device_fixture: MachineModel) -> Generator[MagicMock]:
    """Return a mocked LM client."""
    model = device_fixture

    serial_number = SERIAL_DICT[model]

    dummy_machine = LaMarzoccoMachine(
        model=model,
        serial_number=serial_number,
        name=serial_number,
    )
    config = load_json_object_fixture("config.json", DOMAIN)
    statistics = json.loads(load_fixture("statistics.json", DOMAIN))

    dummy_machine.parse_config(config)
    dummy_machine.parse_statistics(statistics)

    with (
        patch(
            "homeassistant.components.lamarzocco.coordinator.LaMarzoccoMachine",
            autospec=True,
        ) as lamarzocco_mock,
    ):
        lamarzocco = lamarzocco_mock.return_value

        lamarzocco.name = dummy_machine.name
        lamarzocco.model = dummy_machine.model
        lamarzocco.serial_number = dummy_machine.serial_number
        lamarzocco.full_model_name = dummy_machine.full_model_name
        lamarzocco.config = dummy_machine.config
        lamarzocco.statistics = dummy_machine.statistics
        lamarzocco.firmware = dummy_machine.firmware
        lamarzocco.steam_level = SteamLevel.LEVEL_1

        lamarzocco.firmware[FirmwareType.GATEWAY].latest_version = "v3.5-rc3"
        lamarzocco.firmware[FirmwareType.MACHINE].latest_version = "1.55"

        yield lamarzocco


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto mock bluetooth."""


@pytest.fixture
def mock_ble_device() -> BLEDevice:
    """Return a mock BLE device."""
    return BLEDevice(
        "00:00:00:00:00:00", "GS_GS01234", details={"path": "path"}, rssi=50
    )
