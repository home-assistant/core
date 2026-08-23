"""Test the Kostal Plenticore Solar Inverter select platform."""

from pykoplenti import SettingsData
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

pytestmark = [
    pytest.mark.usefixtures("mock_plenticore_client"),
]


async def test_select_battery_charging_usage_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_get_settings: dict[str, list[SettingsData]],
) -> None:
    """Test battery charging usage select is added when settings available."""

    mock_get_settings["devices:local"].extend(
        [
            SettingsData(
                min=None,
                max=None,
                default=None,
                access="readwrite",
                unit=None,
                id="Battery:SmartBatteryControl:Enable",
                type="string",
            ),
            SettingsData(
                min=None,
                max=None,
                default=None,
                access="readwrite",
                unit=None,
                id="Battery:TimeControl:Enable",
                type="string",
            ),
        ]
    )

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_is_registered("select.scb_battery_charging_usage_mode")

    entity = entity_registry.async_get("select.scb_battery_charging_usage_mode")
    assert entity.capabilities.get("options") == [
        "None",
        "Battery:SmartBatteryControl:Enable",
        "Battery:TimeControl:Enable",
    ]


async def test_select_battery_charging_usage_excess_energy_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_get_settings: dict[str, list[SettingsData]],
    mock_get_setting_values: dict[str, dict[str, str]],
) -> None:
    """Test battery charging usage select contains excess AC energy option."""

    mock_get_settings["devices:local"].extend(
        [
            SettingsData(
                min=None,
                max=None,
                default=None,
                access="readwrite",
                unit=None,
                id="Battery:SmartBatteryControl:Enable",
                type="string",
            ),
            SettingsData(
                min=None,
                max=None,
                default=None,
                access="readwrite",
                unit=None,
                id="Battery:TimeControl:Enable",
                type="string",
            ),
        ]
    )

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_is_registered("select.scb_battery_charging_usage_mode")

    entity = entity_registry.async_get("select.scb_battery_charging_usage_mode")
    assert entity.capabilities.get("options") == [
        "None",
        "Battery:SmartBatteryControl:Enable",
        "Battery:TimeControl:Enable",
    ]


async def test_select_battery_charging_usage_not_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test battery charging usage select is not added when settings unavailable."""

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not entity_registry.async_is_registered(
        "select.scb_battery_charging_usage_mode"
    )
