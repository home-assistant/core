"""Test the Kostal Plenticore Solar Inverter select platform."""
from pykoplenti import SettingsData

from homeassistant.components.kostal_plenticore.helper import Plenticore
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_select_battery_charging_usage_available(
    hass: HomeAssistant,
    mock_plenticore: Plenticore,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that the battery charging usage select entity is added if the settings are available."""

    mock_plenticore.client.get_settings.return_value = {
        "devices:local": [
            SettingsData({"id": "Battery:SmartBatteryControl:Enable"}),
            SettingsData({"id": "Battery:TimeControl:Enable"}),
        ]
    }

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_is_registered("select.battery_charging_usage_mode")


async def test_select_battery_charging_usage_not_available(
    hass: HomeAssistant,
    mock_plenticore: Plenticore,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that the battery charging usage select entity is not added if the settings are unavailable."""

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not entity_registry.async_is_registered("select.battery_charging_usage_mode")
