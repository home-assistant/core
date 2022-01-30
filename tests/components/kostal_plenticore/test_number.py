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
        fmt_from="format_round",
        fmt_to="format_round_back",
    )


async def test_setup_all_entries(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_plenticore: MagicMock
):
    """Test if all available entries are setup up."""
    mock_plenticore.client.get_settings.return_value = {
        "devices:local": [
            SettingsData({"id": "Battery:MinSoc"}),
            SettingsData({"id": "Battery:MinHomeComsumption"}),
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
):
    """Test if value property on PlenticoreDataNumber returns an int if available."""

    mock_coordinator.data = {"moduleid": {"dataid": "42"}}

    entity = PlenticoreDataNumber(
        mock_coordinator, "42", "scb", None, mock_number_description
    )

    assert entity.value == 42
    assert type(entity.value) == int


def test_number_returns_none_if_unavailable(
    mock_coordinator: MagicMock,
    mock_number_description: PlenticoreNumberEntityDescription,
):
    """Test if value property on PlenticoreDataNumber returns none if unavailable."""

    mock_coordinator.data = {}  # makes entity not available

    entity = PlenticoreDataNumber(
        mock_coordinator, "42", "scb", None, mock_number_description
    )

    assert entity.value is None


async def test_set_value(
    mock_coordinator: MagicMock,
    mock_number_description: PlenticoreNumberEntityDescription,
):
    """Test if set value calls coordinator with new value."""

    entity = PlenticoreDataNumber(
        mock_coordinator, "42", "scb", None, mock_number_description
    )

    await entity.async_set_value(42)

    mock_coordinator.async_write_data.assert_called_once_with(
        "moduleid", {"dataid": "42"}
    )
    mock_coordinator.async_refresh.assert_called_once()
