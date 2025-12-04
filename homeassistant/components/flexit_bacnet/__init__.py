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
    fireplace_switch_unique_id = f"{coordinator.device.serial_number}-fireplace_mode"
    climate_unique_id = coordinator.device.serial_number

    # Look up the fireplace switch entity by unique_id
    fireplace_switch_entity_id = entity_reg.async_get_entity_id(
        Platform.SWITCH, DOMAIN, fireplace_switch_unique_id
    )

    if fireplace_switch_entity_id:
        entity_entry = entity_reg.async_get(fireplace_switch_entity_id)
        if entity_entry and not entity_entry.disabled:
            # Look up the climate entity by unique_id
            climate_entity_id = entity_reg.async_get_entity_id(
                Platform.CLIMATE, DOMAIN, climate_unique_id
            )
            if climate_entity_id:
                async_create_issue(
                    hass,
                    DOMAIN,
                    f"deprecated_switch_{fireplace_switch_unique_id}",
                    is_fixable=False,
                    issue_domain=DOMAIN,
                    severity=IssueSeverity.WARNING,
                    translation_key="deprecated_fireplace_switch",
                    translation_placeholders={
                        "entity_id": fireplace_switch_entity_id,
                        "climate_entity_id": climate_entity_id,
                    },
                )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: FlexitConfigEntry) -> bool:
    """Unload the Flexit Nordic (BACnet) config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
