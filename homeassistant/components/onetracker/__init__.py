# """The onetracker component."""
# from __future__ import annotations
# import json

# from typing import Any
# from .parcel import ParcelEntity

# # import voluptuous as vol

# from homeassistant.config_entries import ConfigType, ConfigEntry
# from homeassistant.const import CONF_EMAIL, CONF_NAME, CONF_PASSWORD, CONF_SCAN_INTERVAL
# from homeassistant.core import HomeAssistant

# from .const import DEFAULT_NAME, DEFAULT_SCAN_INTERVAL, DOMAIN
# from .coordinator import OneTrackerDataUpdateCoordinator

# import logging

# _LOGGER = logging.getLogger(__name__)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hello World from a config entry."""

    # This creates each HA object for each platform your device requires.
    # It's done by calling the `async_setup_entry` function in each platform module.
    hass.config_entries.async_setup_platforms(entry, ["sensor"])
    return True


# # async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
# #     """Configure setup for OneTracker integration."""
# #     # if config is not None:
# #     #     options = {
# #     #         vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
# #     #         vol.Required(CONF_EMAIL): str,
# #     #         vol.Required(CONF_PASSWORD): str,
# #     #         vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
# #     #     }
# #     #     _LOGGER.warning("Pre async_start")
# #     #     await hass.async_start()
# #     options = hass.data
# #     _LOGGER.warning("Config %s", json.dumps(config))
# #     _LOGGER.warning("Options %s", options)
# #     coordinator = OneTrackerDataUpdateCoordinator(hass, config=config)
# #     await coordinator.async_config_entry_first_refresh()
# #     _LOGGER.warning("Post async_config_entry_first_refresh")
# #     # Return boolean to indicate that initialization was successful.
# #     return True


# async def async_setup_entry(
#     hass: HomeAssistant, entry: ConfigEntry
# ):
#     """Config entry example."""
#     # assuming API object stored here by __init__.py
#     # config = hass.data[DOMAIN][entry.entry_id]

#     _LOGGER.warning("Entry %s", json.dumps(entry.as_dict()))
#     config = entry.data
#     _LOGGER.warning("Config %s", config)

#     # Fetch initial data so we have data when entities subscribe
#     #
#     # If the refresh fails, async_config_entry_first_refresh will
#     # raise ConfigEntryNotReady and setup will try again later
#     #
#     # If you do not want to retry setup on failure, use
#     # coordinator.async_refresh() instead
#     #
#     coordinator = OneTrackerDataUpdateCoordinator(hass, config=config)
#     await coordinator.async_config_entry_first_refresh()
#     _LOGGER.warning("Post async_config_entry_first_refresh")
#     _LOGGER.warning("Data %s", coordinator.data)
#     hass.
#     async_add_entities(
#         ParcelEntity(coordinator, parcel) for idx, parcel in enumerate(coordinator.data)
#     )
#     # Return boolean to indicate that initialization was successful.
#     return True


# # async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
# #     """Set up NZBGet from a config entry."""
# #     hass.data.setdefault(DOMAIN, {})

# #     if not entry.options:
# #         options = {
# #             CONF_SCAN_INTERVAL: entry.data.get(
# #                 CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
# #             ),
# #         }
# #         hass.config_entries.async_update_entry(entry, options=options)

# #     coordinator = NZBGetDataUpdateCoordinator(
# #         hass,
# #         config=entry.data,
# #         options=entry.options,
# #     )

# #     await coordinator.async_config_entry_first_refresh()

# #     undo_listener = entry.add_update_listener(_async_update_listener)

# #     hass.data[DOMAIN][entry.entry_id] = {
# #         DATA_COORDINATOR: coordinator,
# #         DATA_UNDO_UPDATE_LISTENER: undo_listener,
# #     }

# #     await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

# #     _async_register_services(hass, coordinator)

# #     return True
