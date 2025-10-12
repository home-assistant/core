"""Test Kostal Plenticore number."""

from collections.abc import Generator, Iterable
from datetime import timedelta
from unittest.mock import patch

from pykoplenti import ApiClient, SettingsData
import pytest

from homeassistant.components.number import (
    ATTR_MAX,
    ATTR_MIN,
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture
def mock_plenticore_client() -> Generator[ApiClient]:
    """Return a patched ExtendedApiClient."""
    with patch(
        "homeassistant.components.kostal_plenticore.coordinator.ExtendedApiClient",
        autospec=True,
    ) as plenticore_client_class:
        yield plenticore_client_class.return_value


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


@pytest.fixture
def mock_get_setting_values(
    mock_plenticore_client: ApiClient,
) -> dict[str, dict[str, str]]:
    """Add a setting value to the given Plenticore client.

    Returns a list with setting values which can be extended by test cases.
    """

    mock_plenticore_client.get_settings.return_value = {
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

    # Add default settings values - this values are always retrieved by the integration on startup
    setting_values = DEFAULT_SETTING_VALUES.copy()

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


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_setup_all_entries(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_plenticore_client: ApiClient,
    mock_get_setting_values: dict[str, dict[str, str]],
) -> None:
    """Test if all available entries are setup."""

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get("number.scb_battery_min_soc") is not None
    assert (
        entity_registry.async_get("number.scb_battery_min_home_consumption") is not None
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_setup_no_entries(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_plenticore_client: ApiClient,
    mock_get_setting_values: dict[str, dict[str, str]],
) -> None:
    """Test that no entries are setup if Plenticore does not provide data."""

    # remove all settings except hostname which is used during setup
    mock_plenticore_client.get_settings.return_value = {
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

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get("number.scb_battery_min_soc") is None
    assert entity_registry.async_get("number.scb_battery_min_home_consumption") is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_number_has_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_plenticore_client: ApiClient,
    mock_get_setting_values: dict[str, dict[str, str]],
) -> None:
    """Test if number has a value if data is provided on update."""

    mock_get_setting_values["devices:local"]["Battery:MinSoc"] = "42"

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=3))
    await hass.async_block_till_done()

    state = hass.states.get("number.scb_battery_min_soc")
    assert state.state == "42"
    assert state.attributes[ATTR_MIN] == 5
    assert state.attributes[ATTR_MAX] == 100


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_number_is_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_plenticore_client: ApiClient,
    mock_get_setting_values: dict[str, dict[str, str]],
) -> None:
    """Test if number is unavailable if no data is provided on update."""

    del mock_get_setting_values["devices:local"]["Battery:MinSoc"]

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=3))
    await hass.async_block_till_done()

    state = hass.states.get("number.scb_battery_min_soc")
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_set_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_plenticore_client: ApiClient,
    mock_get_setting_values: dict[str, dict[str, str]],
) -> None:
    """Test if a new value could be set."""

    mock_get_setting_values["devices:local"]["Battery:MinSoc"] = "42"

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=3))
    await hass.async_block_till_done()

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "number.scb_battery_min_soc",
            ATTR_VALUE: 80,
        },
        blocking=True,
    )

    mock_plenticore_client.set_setting_values.assert_called_once_with(
        "devices:local", {"Battery:MinSoc": "80"}
    )
