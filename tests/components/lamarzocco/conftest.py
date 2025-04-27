"""Lamarzocco session fixtures."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from bleak.backends.device import BLEDevice
from pylamarzocco.const import ModelName
from pylamarzocco.models import (
    Thing,
    ThingDashboardConfig,
    ThingSchedulingSettings,
    ThingSettings,
)
import pytest

from homeassistant.components.lamarzocco.const import DOMAIN
from homeassistant.const import CONF_ADDRESS, CONF_TOKEN
from homeassistant.core import HomeAssistant

from . import SERIAL_DICT, USER_INPUT, async_init_integration

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_config_entry(
    hass: HomeAssistant, mock_lamarzocco: MagicMock
) -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="My LaMarzocco",
        domain=DOMAIN,
        version=3,
        data=USER_INPUT
        | {
            CONF_ADDRESS: "00:00:00:00:00:00",
            CONF_TOKEN: "token",
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
def device_fixture() -> ModelName:
    """Return the device fixture for a specific device."""
    return ModelName.GS3_AV


@pytest.fixture(autouse=True)
def mock_cloud_client() -> Generator[MagicMock]:
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
        client.list_things.return_value = [
            Thing.from_dict(load_json_object_fixture("thing.json", DOMAIN))
        ]
        client.get_thing_settings.return_value = ThingSettings.from_dict(
            load_json_object_fixture("settings.json", DOMAIN)
        )
        yield client


@pytest.fixture
def mock_lamarzocco(device_fixture: ModelName) -> Generator[MagicMock]:
    """Return a mocked LM client."""

    if device_fixture == ModelName.LINEA_MINI:
        config = load_json_object_fixture("config_mini.json", DOMAIN)
    elif device_fixture == ModelName.LINEA_MICRA:
        config = load_json_object_fixture("config_micra.json", DOMAIN)
    else:
        config = load_json_object_fixture("config_gs3.json", DOMAIN)
    schedule = load_json_object_fixture("schedule.json", DOMAIN)
    settings = load_json_object_fixture("settings.json", DOMAIN)

    with (
        patch(
            "homeassistant.components.lamarzocco.LaMarzoccoMachine",
            autospec=True,
        ) as machine_mock_init,
    ):
        machine_mock = machine_mock_init.return_value

        machine_mock.serial_number = SERIAL_DICT[device_fixture]
        machine_mock.dashboard = ThingDashboardConfig.from_dict(config)
        machine_mock.schedule = ThingSchedulingSettings.from_dict(schedule)
        machine_mock.settings = ThingSettings.from_dict(settings)
        machine_mock.dashboard.model_name = device_fixture
        machine_mock.to_dict.return_value = {
            "serial_number": machine_mock.serial_number,
            "dashboard": machine_mock.dashboard.to_dict(),
            "schedule": machine_mock.schedule.to_dict(),
            "settings": machine_mock.settings.to_dict(),
        }
        machine_mock.websocket.disconnect = AsyncMock()
        yield machine_mock


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto mock bluetooth."""


@pytest.fixture
def mock_ble_device() -> BLEDevice:
    """Return a mock BLE device."""
    return BLEDevice(
        "00:00:00:00:00:00", "GS_GS012345", details={"path": "path"}, rssi=50
    )


@pytest.fixture(autouse=True)
def mock_ws_settle_in() -> Generator:
    """Auto mock websocket settle in."""
    with patch(
        "homeassistant.components.lamarzocco.coordinator.WS_SETTLE_IN_TIME", new=0
    ):
        yield
