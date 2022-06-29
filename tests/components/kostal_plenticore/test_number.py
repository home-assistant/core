"""Test Kostal Plenticore number."""

from unittest.mock import AsyncMock, MagicMock

from kostal.plenticore import SettingsData
import pytest

from homeassistant.components.kostal_plenticore.const import (
    PlenticoreNumberEntityDescription,
)
from homeassistant.components.kostal_plenticore.number import PlenticoreDataNumber
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import async_get

from tests.common import MockConfigEntry


@pytest.fixture
def mock_coordinator() -> MagicMock:
    """Return a mocked coordinator for tests."""
    coordinator = MagicMock()
    coordinator.async_write_data = AsyncMock()
    coordinator.async_refresh = AsyncMock()
    return coordinator


@pytest.fixture
def mock_number_description() -> PlenticoreNumberEntityDescription:
    """Return a PlenticoreNumberEntityDescription for tests."""
    return PlenticoreNumberEntityDescription(
        key="mock key",
        module_id="moduleid",
        data_id="dataid",
        native_min_value=0,
        native_max_value=1000,
        fmt_from="format_round",
        fmt_to="format_round_back",
    )


@pytest.fixture
def mock_setting_data() -> SettingsData:
    """Return a default SettingsData for tests."""
    return SettingsData(
        {
            "default": None,
            "min": None,
            "access": None,
            "max": None,
            "unit": None,
            "type": None,
            "id": "data_id",
        }
    )


async def test_setup_all_entries(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_plenticore: MagicMock
):
    """Test if all available entries are setup up."""
    mock_plenticore.client.get_settings.return_value = {
        "devices:local": [
            SettingsData({"id": "Battery:MinSoc", "min": None, "max": None}),
            SettingsData(
                {"id": "Battery:MinHomeComsumption", "min": None, "max": None}
            ),
        ]
    }

    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    ent_reg = async_get(hass)
    assert ent_reg.async_get("number.scb_battery_min_soc") is not None
    assert ent_reg.async_get("number.scb_battery_min_home_consumption") is not None


async def test_setup_no_entries(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_plenticore: MagicMock
):
    """Test that no entries are setup up."""
    mock_plenticore.client.get_settings.return_value = []
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    ent_reg = async_get(hass)
    assert ent_reg.async_get("number.scb_battery_min_soc") is None
    assert ent_reg.async_get("number.scb_battery_min_home_consumption") is None


def test_number_returns_value_if_available(
    mock_coordinator: MagicMock,
    mock_number_description: PlenticoreNumberEntityDescription,
    mock_setting_data: SettingsData,
):
    """Test if value property on PlenticoreDataNumber returns an int if available."""

    mock_coordinator.data = {"moduleid": {"dataid": "42"}}

    entity = PlenticoreDataNumber(
        mock_coordinator, "42", "scb", None, mock_number_description, mock_setting_data
    )

    assert entity.value == 42
    assert type(entity.value) == int


def test_number_returns_none_if_unavailable(
    mock_coordinator: MagicMock,
    mock_number_description: PlenticoreNumberEntityDescription,
    mock_setting_data: SettingsData,
):
    """Test if value property on PlenticoreDataNumber returns none if unavailable."""

    mock_coordinator.data = {}  # makes entity not available

    entity = PlenticoreDataNumber(
        mock_coordinator, "42", "scb", None, mock_number_description, mock_setting_data
    )

    assert entity.value is None


async def test_set_value(
    mock_coordinator: MagicMock,
    mock_number_description: PlenticoreNumberEntityDescription,
    mock_setting_data: SettingsData,
):
    """Test if set value calls coordinator with new value."""

    entity = PlenticoreDataNumber(
        mock_coordinator, "42", "scb", None, mock_number_description, mock_setting_data
    )

    await entity.async_set_native_value(42)

    mock_coordinator.async_write_data.assert_called_once_with(
        "moduleid", {"dataid": "42"}
    )
    mock_coordinator.async_refresh.assert_called_once()


async def test_minmax_overwrite(
    mock_coordinator: MagicMock,
    mock_number_description: PlenticoreNumberEntityDescription,
):
    """Test if min/max value is overwritten from retrieved settings data."""

    setting_data = SettingsData(
        {
            "min": "5",
            "max": "100",
        }
    )

    entity = PlenticoreDataNumber(
        mock_coordinator, "42", "scb", None, mock_number_description, setting_data
    )

    assert entity.min_value == 5
    assert entity.max_value == 100


async def test_added_to_hass(
    mock_coordinator: MagicMock,
    mock_number_description: PlenticoreNumberEntityDescription,
    mock_setting_data: SettingsData,
):
    """Test if coordinator starts fetching after added to hass."""

    entity = PlenticoreDataNumber(
        mock_coordinator, "42", "scb", None, mock_number_description, mock_setting_data
    )

    await entity.async_added_to_hass()

    mock_coordinator.start_fetch_data.assert_called_once_with("moduleid", "dataid")


async def test_remove_from_hass(
    mock_coordinator: MagicMock,
    mock_number_description: PlenticoreNumberEntityDescription,
    mock_setting_data: SettingsData,
):
    """Test if coordinator stops fetching after remove from hass."""

    entity = PlenticoreDataNumber(
        mock_coordinator, "42", "scb", None, mock_number_description, mock_setting_data
    )

    await entity.async_will_remove_from_hass()

    mock_coordinator.stop_fetch_data.assert_called_once_with("moduleid", "dataid")
