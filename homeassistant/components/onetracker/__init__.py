"""The onetracker component."""
from __future__ import annotations

from typing import Any

# import voluptuous as vol

from homeassistant.config_entries import ConfigType
from homeassistant.const import CONF_EMAIL, CONF_NAME, CONF_PASSWORD, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant

from .const import DEFAULT_NAME, DEFAULT_SCAN_INTERVAL
from .coordinator import OneTrackerDataUpdateCoordinator


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Configure setup for OneTracker integration."""
    if config is not None:
        # options = {
        #     vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
        #     vol.Required(CONF_EMAIL): str,
        #     vol.Required(CONF_PASSWORD): str,
        #     vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
        # }

        hass.async_start()

    coordinator = OneTrackerDataUpdateCoordinator(hass, config=config)
    await coordinator.async_config_entry_first_refresh()
    # Return boolean to indicate that initialization was successful.
    return True


# async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
#     """Set up NZBGet from a config entry."""
#     hass.data.setdefault(DOMAIN, {})

#     if not entry.options:
#         options = {
#             CONF_SCAN_INTERVAL: entry.data.get(
#                 CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
#             ),
#         }
#         hass.config_entries.async_update_entry(entry, options=options)

#     coordinator = NZBGetDataUpdateCoordinator(
#         hass,
#         config=entry.data,
#         options=entry.options,
#     )

#     await coordinator.async_config_entry_first_refresh()

#     undo_listener = entry.add_update_listener(_async_update_listener)

#     hass.data[DOMAIN][entry.entry_id] = {
#         DATA_COORDINATOR: coordinator,
#         DATA_UNDO_UPDATE_LISTENER: undo_listener,
#     }

#     await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

#     _async_register_services(hass, coordinator)

#     return True
