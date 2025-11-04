"""The Flexit Nordic (BACnet) integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import DOMAIN
from .coordinator import FlexitConfigEntry, FlexitCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: FlexitConfigEntry) -> bool:
    """Set up Flexit Nordic (BACnet) from a config entry."""

    coordinator = FlexitCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Check if deprecated fireplace switch is enabled and create repair issue
    entity_reg = er.async_get(hass)
    fireplace_switch_id = f"{coordinator.device.serial_number}-fireplace_mode"

    # Look for the fireplace switch entity
    for entity in er.async_entries_for_config_entry(entity_reg, entry.entry_id):
        if entity.unique_id == fireplace_switch_id and not entity.disabled:
            # Switch is enabled, create deprecation issue
            climate_entity_id = entity.entity_id.replace("switch.", "climate.").replace(
                "_fireplace_mode", ""
            )
            async_create_issue(
                hass,
                DOMAIN,
                f"deprecated_switch_{entity.unique_id}",
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=IssueSeverity.WARNING,
                translation_key="deprecated_fireplace_switch",
                translation_placeholders={
                    "entity_id": entity.entity_id,
                    "climate_entity_id": climate_entity_id,
                },
            )
            break

    return True


async def async_unload_entry(hass: HomeAssistant, entry: FlexitConfigEntry) -> bool:
    """Unload the Flexit Nordic (BACnet) config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
