"""The rejseplanen component."""

from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import RejseplanenConfigEntry, RejseplanenDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RejseplanenConfigEntry,
) -> bool:
    """Set up Rejseplanen from a config entry."""
    coordinator = RejseplanenDataUpdateCoordinator(
        hass,
        config_entry,
    )
    config_entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(
        config_entry, [Platform.SENSOR]
    )
    config_entry.async_on_unload(
        config_entry.add_update_listener(_async_update_listener)
    )
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    config_entry: RejseplanenConfigEntry,
) -> bool:
    """Unload a config entry."""
    _LOGGER.debug(
        "Unloading Rejseplanen integration for entry: %s", config_entry.entry_id
    )
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


async def _async_update_listener(
    hass: HomeAssistant,
    config_entry: RejseplanenConfigEntry,
) -> None:
    """Handle update."""
    _LOGGER.debug("Update listener triggered for entry: %s", config_entry.entry_id)
    await hass.config_entries.async_reload(config_entry.entry_id)


# async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
#     """Warn if Rejseplanen is configured via YAML sensor platform."""
#     if "sensor" in config:
#         for entry in config["sensor"]:
#             if entry.get("platform") == DOMAIN:
#                 # Found a deprecated YAML config for Rejseplanen
#                 _LOGGER.warning(
#                     "Configuration of Rejseplanen via configuration.yaml is deprecated and will be ignored"
#                     " Please use the UI to configure the integration"
#                 )
#                 async_create_issue(
#                     hass,
#                     DOMAIN,
#                     "rp_yaml_deprecated",
#                     is_fixable=False,
#                     is_persistent=True,
#                     severity=IssueSeverity.WARNING,
#                     translation_key="yaml_deprecated",
#                 )
#                 break
#     return True
