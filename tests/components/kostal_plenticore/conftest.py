"""Fixtures for Kostal Plenticore tests."""

from __future__ import annotations

from collections.abc import Generator, Iterable
import copy
from unittest.mock import AsyncMock, MagicMock, patch

from pykoplenti import ApiClient, ExtendedApiClient, MeData, SettingsData, VersionData
import pytest

from homeassistant.components.kostal_plenticore.coordinator import Plenticore
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo

from tests.common import MockConfigEntry

DEFAULT_SETTING_VALUES = {
    "devices:local": {
        "Properties:StringCnt": "2",
        "EnergySensor:SensorPosition": "1",
        "EnergySensor:InstalledSensor": "1",
        "Battery:Type": "0",
        "Properties:String0Features": "1",
        "Properties:String1Features": "1",
        "Properties:SerialNo": "42",
        "Branding:ProductName1": "PLENTICORE",
        "Branding:ProductName2": "plus 10",
        "Properties:VersionIOC": "01.45",
        "Properties:VersionMC": " 01.46",
        "Battery:MinSoc": "5",
        "Battery:MinHomeComsumption": "50",
    },
    "scb:network": {"Hostname": "scb"},
}

DEFAULT_SETTINGS = {
    "devices:local": [
        SettingsData(
            min="5",
            max="100",
            default=None,
            access="readwrite",
            unit="%",
            id="Battery:MinSoc",
            type="byte",
        ),
        SettingsData(
            min="50",
            max="38000",
            default=None,
            access="readwrite",
            unit="W",
            id="Battery:MinHomeComsumption",
            type="byte",
        ),
    ],
    "scb:network": [
        SettingsData(
            min="1",
            max="63",
            default=None,
            access="readwrite",
            unit=None,
            id="Hostname",
            type="string",
        )
    ],
}


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked ConfigEntry for testing."""
    return MockConfigEntry(
        entry_id="2ab8dd92a62787ddfe213a67e09406bd",
        title="scb",
        domain="kostal_plenticore",
        data={"host": "192.168.1.2", "password": "SecretPassword"},
    )


@pytest.fixture
def mock_installer_config_entry() -> MockConfigEntry:
    """Return a mocked ConfigEntry for testing with installer login."""
    return MockConfigEntry(
        entry_id="2ab8dd92a62787ddfe213a67e09406bd",
        title="scb",
        domain="kostal_plenticore",
        data={
            "host": "192.168.1.2",
            "password": "secret_password",
            "service_code": "12345",
        },
    )


@pytest.fixture
def mock_plenticore() -> Generator[Plenticore]:
    """Set up a Plenticore mock with some default values."""
    with patch(
        "homeassistant.components.kostal_plenticore.Plenticore", autospec=True
    ) as mock_api_class:
        # setup
        plenticore = mock_api_class.return_value
        plenticore.async_setup = AsyncMock()
        plenticore.async_setup.return_value = True

        plenticore.device_info = DeviceInfo(
            configuration_url="http://192.168.1.2",
            identifiers={("kostal_plenticore", "12345")},
            manufacturer="Kostal",
            model="PLENTICORE plus 10",
            name="scb",
            sw_version="IOC: 01.45 MC: 01.46",
        )

        plenticore.client = MagicMock()

        plenticore.client.get_version = AsyncMock()
        plenticore.client.get_version.return_value = VersionData(
            api_version="0.2.0",
            hostname="scb",
            name="PUCK RESTful API",
            sw_version="01.16.05025",
        )

        plenticore.client.get_me = AsyncMock()
        plenticore.client.get_me.return_value = MeData(
            locked=False,
            active=True,
            authenticated=True,
            permissions=[],
            anonymous=False,
            role="USER",
        )

        plenticore.client.get_process_data = AsyncMock(return_value={})
        plenticore.client.get_settings = AsyncMock(return_value={})
        plenticore.client.get_setting_values = AsyncMock(return_value={})

        yield plenticore


@pytest.fixture
def mock_plenticore_client() -> Generator[ExtendedApiClient]:
    """Return a patched ExtendedApiClient."""
    with patch(
        "homeassistant.components.kostal_plenticore.coordinator.ExtendedApiClient",
        autospec=True,
    ) as plenticore_client_class:
        yield plenticore_client_class.return_value


@pytest.fixture
def mock_get_settings(
    mock_plenticore_client: ApiClient,
) -> dict[str, list[SettingsData]]:
    """Add setting data to mock_plenticore_client.

    Returns a dictionary with setting data which can be mutated by test cases.
    """
    settings = copy.deepcopy(DEFAULT_SETTINGS)
    mock_plenticore_client.get_settings.return_value = settings
    return settings


@pytest.fixture
def mock_get_setting_values(
    mock_plenticore_client: ApiClient,
) -> dict[str, dict[str, str]]:
    """Add setting values to mock_plenticore_client.

    Returns a dictionary with setting values which can be mutated by test cases.
    """
    # Add default settings values - this values are always retrieved by the integration on startup
    setting_values = copy.deepcopy(DEFAULT_SETTING_VALUES)

    def default_settings_data(*args):
        # the get_setting_values method can be called with different argument types and numbers
        match args:
            case (str() as module_id, str() as data_id):
                request = {module_id: [data_id]}
            case (str() as module_id, Iterable() as data_ids):
                request = {module_id: data_ids}
            case ({},):
                request = args[0]
            case _:
                raise NotImplementedError

        result = {}
        for module_id, data_ids in request.items():
            if (values := setting_values.get(module_id)) is not None:
                result[module_id] = {}
                for data_id in data_ids:
                    if data_id in values:
                        result[module_id][data_id] = values[data_id]
                    else:
                        raise ValueError(
                            f"Missing data_id {data_id} in module {module_id}"
                        )
            else:
                raise ValueError(f"Missing module_id {module_id}")

        return result

    mock_plenticore_client.get_setting_values.side_effect = default_settings_data

    return setting_values


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up Kostal Plenticore integration for testing."""

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
