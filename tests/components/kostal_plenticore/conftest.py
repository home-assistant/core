"""Fixtures for Kostal Plenticore tests."""

from __future__ import annotations

from collections.abc import Generator, Iterable
import copy
from unittest.mock import patch

from pykoplenti import ExtendedApiClient, MeData, SettingsData, VersionData
import pytest

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

DEFAULT_SETTING_VALUES = {
    "devices:local": {
        "Properties:StringCnt": "2",
        "Properties:String0Features": "1",
        "Properties:String1Features": "1",
        "Properties:SerialNo": "42",
        "Branding:ProductName1": "PLENTICORE",
        "Branding:ProductName2": "plus 10",
        "Properties:VersionIOC": "01.45",
        "Properties:VersionMC": "01.46",
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
def mock_get_settings() -> dict[str, list[SettingsData]]:
    """Add setting data to mock_plenticore_client.

    Returns a dictionary with setting data which can be mutated by test cases.
    """
    return copy.deepcopy(DEFAULT_SETTINGS)


@pytest.fixture
def mock_get_setting_values() -> dict[str, dict[str, str]]:
    """Add setting values to mock_plenticore_client.

    Returns a dictionary with setting values which can be mutated by test cases.
    """
    # Add default settings values - this values are always retrieved by the integration on startup
    return copy.deepcopy(DEFAULT_SETTING_VALUES)


@pytest.fixture
def mock_plenticore_client(
    mock_get_settings: dict[str, list[SettingsData]],
    mock_get_setting_values: dict[str, dict[str, str]],
) -> Generator[ExtendedApiClient]:
    """Return a patched ExtendedApiClient."""
    with patch(
        "homeassistant.components.kostal_plenticore.coordinator.ExtendedApiClient",
        autospec=True,
    ) as plenticore_client_class:

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
                if (values := mock_get_setting_values.get(module_id)) is not None:
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

        client = plenticore_client_class.return_value
        client.get_setting_values.side_effect = default_settings_data
        client.get_settings.return_value = mock_get_settings
        client.get_me.return_value = MeData(
            locked=False,
            active=True,
            authenticated=True,
            permissions=[],
            anonymous=False,
            role="USER",
        )
        client.get_version.return_value = VersionData(
            api_version="0.2.0",
            hostname="scb",
            name="PUCK RESTful API",
            sw_version="01.16.05025",
        )

        yield client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up Kostal Plenticore integration for testing."""

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
