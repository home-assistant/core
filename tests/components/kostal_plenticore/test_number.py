"""Test Kostal Plenticore number."""

from unittest.mock import AsyncMock, MagicMock

from kostal.plenticore import SettingsData
import pytest

from homeassistant.components.kostal_plenticore.number import (
    PlenticoreNumberEntityDescription,
)
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
