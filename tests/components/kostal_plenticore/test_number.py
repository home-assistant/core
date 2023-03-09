"""Test Kostal Plenticore number."""

from collections.abc import Generator
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
from homeassistant.helpers.entity_registry import async_get
from homeassistant.util import dt

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.fixture
def mock_plenticore_client() -> Generator[ApiClient, None, None]:
    """Return a patched ApiClient."""
    with patch(
        "homeassistant.components.kostal_plenticore.helper.ApiClient",
        autospec=True,
    ) as plenticore_client_class:
        yield plenticore_client_class.return_value


@pytest.fixture
def mock_get_setting_values(mock_plenticore_client: ApiClient) -> list:
    """Add a setting value to the given Plenticore client.

    Returns a list with setting values which can be extended by test cases.
    """

    mock_plenticore_client.get_settings.return_value = {
        "devices:local": [
            SettingsData(
                {
                    "default": None,
                    "min": 5,
                    "max": 100,
                    "access": "readwrite",
                    "unit": "%",
                    "type": "byte",
                    "id": "Battery:MinSoc",
                }
            ),
            SettingsData(
                {
                    "default": None,
                    "min": 50,
                    "max": 38000,
                    "access": "readwrite",
                    "unit": "W",
                    "type": "byte",
                    "id": "Battery:MinHomeComsumption",
                }
            ),
        ]
    }

    # this values are always retrieved by the integration on startup
    setting_values = [
        {
            "devices:local": {
                "Properties:SerialNo": "42",
                "Branding:ProductName1": "PLENTICORE",
                "Branding:ProductName2": "plus 10",
                "Properties:VersionIOC": "01.45",
                "Properties:VersionMC": " 01.46",
            },
            "scb:network": {"Hostname": "scb"},
        }
    ]

    mock_plenticore_client.get_setting_values.side_effect = setting_values

    return setting_values


async def test_setup_all_entries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_plenticore_client: ApiClient,
    mock_get_setting_values: list,
    entity_registry_enabled_by_default,
) -> None:
    """Test if all available entries are setup."""

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    ent_reg = async_get(hass)
    assert ent_reg.async_get("number.scb_battery_min_soc") is not None
    assert ent_reg.async_get("number.scb_battery_min_home_consumption") is not None


async def test_setup_no_entries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_plenticore_client: ApiClient,
    mock_get_setting_values: list,
    entity_registry_enabled_by_default,
) -> None:
    """Test that no entries are setup if Plenticore does not provide data."""

    mock_plenticore_client.get_settings.return_value = []

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    ent_reg = async_get(hass)
    assert ent_reg.async_get("number.scb_battery_min_soc") is None
    assert ent_reg.async_get("number.scb_battery_min_home_consumption") is None


async def test_number_has_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_plenticore_client: ApiClient,
    mock_get_setting_values: list,
    entity_registry_enabled_by_default,
) -> None:
    """Test if number has a value if data is provided on update."""

    mock_get_setting_values.append({"devices:local": {"Battery:MinSoc": "42"}})

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    async_fire_time_changed(hass, dt.utcnow() + timedelta(seconds=3))
    await hass.async_block_till_done()

    state = hass.states.get("number.scb_battery_min_soc")
    assert state.state == "42"
    assert state.attributes[ATTR_MIN] == 5
    assert state.attributes[ATTR_MAX] == 100


async def test_number_is_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_plenticore_client: ApiClient,
    mock_get_setting_values: list,
    entity_registry_enabled_by_default,
) -> None:
    """Test if number is unavailable if no data is provided on update."""

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    async_fire_time_changed(hass, dt.utcnow() + timedelta(seconds=3))
    await hass.async_block_till_done()

    state = hass.states.get("number.scb_battery_min_soc")
    assert state.state == STATE_UNAVAILABLE


async def test_set_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_plenticore_client: ApiClient,
    mock_get_setting_values: list,
    entity_registry_enabled_by_default,
) -> None:
    """Test if a new value could be set."""

    mock_get_setting_values.append({"devices:local": {"Battery:MinSoc": "42"}})

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    async_fire_time_changed(hass, dt.utcnow() + timedelta(seconds=3))
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
