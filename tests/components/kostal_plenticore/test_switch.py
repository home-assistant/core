"""Test the Kostal Plenticore Solar Inverter switch platform."""

from pykoplenti import SettingsData

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_installer_setting_not_available(
    hass: HomeAssistant,
    mock_get_settings: dict[str, list[SettingsData]],
    mock_get_setting_values: dict[str, dict[str, str]],
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that the manual charge setting is not available when not using the installer login."""
    mock_get_settings.update(
        {
            "devices:local": [
                SettingsData(
                    min=None,
                    max=None,
                    default=None,
                    access="readwrite",
                    unit=None,
                    id="Battery:ManualCharge",
                    type="bool",
                )
            ]
        }
    )

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not entity_registry.async_is_registered("switch.scb_battery_manual_charge")


async def test_installer_setting_available(
    hass: HomeAssistant,
    mock_get_settings: dict[str, list[SettingsData]],
    mock_get_setting_values: dict[str, dict[str, str]],
    mock_installer_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that the manual charge setting is available when using the installer login."""
    mock_get_settings.update(
        {
            "devices:local": [
                SettingsData(
                    min=None,
                    max=None,
                    default=None,
                    access="readwrite",
                    unit=None,
                    id="Battery:ManualCharge",
                    type="bool",
                )
            ]
        }
    )

    mock_installer_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_installer_config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_is_registered("switch.scb_battery_manual_charge")
