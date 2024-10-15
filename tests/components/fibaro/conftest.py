"""Test helpers."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.fibaro import CONF_IMPORT_PLUGINS, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_SERIALNUMBER = "HC2-111111"
TEST_NAME = "my_fibaro_home_center"
TEST_URL = "http://192.168.1.1/api/"
TEST_USERNAME = "user"
TEST_PASSWORD = "password"
TEST_VERSION = "4.360"
TEST_MODEL = "HC3"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.fibaro.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_scene() -> Mock:
    """Fixture for an individual scene."""
    scene = Mock()
    scene.fibaro_id = 1
    scene.name = "Test scene"
    scene.room_id = 1
    scene.visible = True
    return scene


@pytest.fixture
def mock_room() -> Mock:
    """Fixture for an individual room."""
    room = Mock()
    room.fibaro_id = 1
    room.name = "Room 1"
    return room


@pytest.fixture
def mock_power_sensor() -> Mock:
    """Fixture for an individual power sensor without value."""
    sensor = Mock()
    sensor.fibaro_id = 1
    sensor.parent_fibaro_id = 0
    sensor.name = "Test sensor"
    sensor.room_id = 1
    sensor.visible = True
    sensor.enabled = True
    sensor.type = "com.fibaro.powerMeter"
    sensor.base_type = "com.fibaro.device"
    sensor.properties = {
        "zwaveCompany": "Goap",
        "endPointId": "2",
        "manufacturer": "",
        "power": "6.60",
    }
    sensor.actions = {}
    sensor.has_central_scene_event = False
    value_mock = Mock()
    value_mock.has_value = False
    value_mock.is_bool_value = False
    sensor.value = value_mock
    return sensor


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_URL: TEST_URL,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_IMPORT_PLUGINS: True,
        },
    )
    mock_config_entry.add_to_hass(hass)
    return mock_config_entry


@pytest.fixture
def mock_fibaro_client() -> Generator[Mock]:
    """Return a mocked FibaroClient."""
    info_mock = Mock()
    info_mock.serial_number = TEST_SERIALNUMBER
    info_mock.hc_name = TEST_NAME
    info_mock.current_version = TEST_VERSION
    info_mock.platform = TEST_MODEL

    with patch(
        "homeassistant.components.fibaro.FibaroClient", autospec=True
    ) as fibaro_client_mock:
        client = fibaro_client_mock.return_value
        client.set_authentication.return_value = None
        client.connect.return_value = True
        client.read_info.return_value = info_mock
        client.read_rooms.return_value = []
        client.read_scenes.return_value = []
        client.read_devices.return_value = []
        client.register_update_handler.return_value = None
        client.unregister_update_handler.return_value = None
        yield client


async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Set up the fibaro integration for testing."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
