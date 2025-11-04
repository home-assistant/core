"""The rejseplanen component."""

from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import RejseplanenConfigEntry, RejseplanenDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Set py_rejseplan library to WARNING level by default to reduce log noise
# Users can override in configuration.yaml with: py_rejseplan: debug
logging.getLogger("py_rejseplan").setLevel(logging.WARNING)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Rejseplanen component from YAML (deprecated)."""
    if DOMAIN in config:
        # Create a repair issue to inform users to remove YAML configuration
        ir.async_create_issue(
            hass,
            DOMAIN,
            "yaml_deprecated",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="yaml_deprecated",
        )
        _LOGGER.warning(
            "YAML configuration for Rejseplanen is deprecated. "
            "Please remove the rejseplanen entry from your configuration.yaml "
            "and set up the integration through the UI"
        )

    return True


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RejseplanenConfigEntry,
) -> bool:
    """Set up Rejseplanen from a config entry."""
    coordinator = RejseplanenDataUpdateCoordinator(hass, config_entry)
    config_entry.runtime_data = coordinator

    # ✅ Create the service device entry
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, config_entry.entry_id)},
        name="Rejseplanen",
        manufacturer="Rejseplanen",
        model="Public transport API",
        entry_type=DeviceEntryType.SERVICE,
        configuration_url="https://www.rejseplanen.dk/",
    )

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as ex:
        raise ConfigEntryNotReady(f"Unable to connect to Rejseplanen API: {ex}") from ex

    # ✅ Register update listener for subentry changes - but use minimal reload
    config_entry.async_on_unload(
        config_entry.add_update_listener(_async_update_listener)
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    config_entry: RejseplanenConfigEntry,
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


async def _async_update_listener(
    hass: HomeAssistant,
    config_entry: RejseplanenConfigEntry,
) -> None:
    """Handle update when subentries are added/removed."""
    _LOGGER.debug("Update listener triggered for entry: %s", config_entry.entry_id)

    # ✅ Instead of setting up platforms again, reload the entire config entry
    # This is the standard approach for handling subentry changes
    await hass.config_entries.async_reload(config_entry.entry_id)
