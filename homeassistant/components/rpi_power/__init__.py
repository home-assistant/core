"""The Raspberry Pi Power Supply Checker integration."""

from rpi_bad_power import UnderVoltage, new_under_voltage

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN, ISSUE_UNDER_VOLTAGE

PLATFORMS = [Platform.BINARY_SENSOR]

type RpiPowerConfigEntry = ConfigEntry[UnderVoltage]


async def async_setup_entry(hass: HomeAssistant, entry: RpiPowerConfigEntry) -> None:
    """Set up Raspberry Pi Power Supply Checker from a config entry."""
    # Link an issue raised before issues were linked to their entry
    if (
        issue := ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_UNDER_VOLTAGE)
    ) and issue.config_entry_id is None:
        ir.async_create_issue(
            hass,
            DOMAIN,
            ISSUE_UNDER_VOLTAGE,
            config_entry_id=entry.entry_id,
            is_fixable=True,
            is_persistent=True,
            severity=ir.IssueSeverity.CRITICAL,
            translation_key=ISSUE_UNDER_VOLTAGE,
        )

    if (client := await hass.async_add_executor_job(new_under_voltage)) is None:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="under_voltage_not_supported",
        )

    entry.runtime_data = client

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: RpiPowerConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: RpiPowerConfigEntry) -> None:
    """Remove a config entry."""
    # Issues raised before they were linked to the entry outlive it otherwise
    ir.async_delete_issue(hass, DOMAIN, ISSUE_UNDER_VOLTAGE)
