"""The Opower integration."""

from opower import select_utility

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import CONF_UTILITY, DOMAIN
from .coordinator import OpowerConfigEntry, OpowerCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: OpowerConfigEntry) -> bool:
    """Set up Opower from a config entry."""
    utility_name = entry.data[CONF_UTILITY]

    # Check for National Grid and create an issue if the user needs
    # to migrate to the new integration. Do this before validating
    # the utility to recommend the new integration once support is
    # removed from the opower library.
    if utility_name.startswith("National Grid"):
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"national_grid_migration_{entry.entry_id}",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="national_grid_migration",
            translation_placeholders={
                "utility": utility_name,
                "add_integration": "/config/integrations/dashboard/add?domain=national_grid_us",
            },
        )

    try:
        select_utility(utility_name)
    except ValueError:
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"unsupported_utility_{entry.entry_id}",
            is_fixable=True,
            severity=ir.IssueSeverity.ERROR,
            translation_key="unsupported_utility",
            translation_placeholders={"utility": utility_name},
            data={
                "entry_id": entry.entry_id,
                "utility": utility_name,
                "title": entry.title,
            },
        )
        return False

    coordinator = OpowerCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: OpowerConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
