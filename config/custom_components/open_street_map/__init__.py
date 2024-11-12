"""The OpenStreetMap integration."""

from __future__ import annotations

# from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

# TODO List the platforms that you want to support. # pylint: disable=fixme
# For your initial PR, limit it to 1 platform.
# PLATFORMS: list[Platform] = [Platform.LIGHT]
PLATFORMS: list[Platform] = []

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# TODO Create ConfigEntry type alias with API object
# TODO Rename type alias and update all entry annotations
# type OpenStreetMapConfigEntry = ConfigEntry[MyApi]  # noqa: F821


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the OpenStreetMap integration."""
    # Initialize the domain-specific data
    hass.data[DOMAIN] = {}

    # Optionally, set a state or initialize any service here
    hass.states.async_set(f"{DOMAIN}.integration", "loaded")

    return True


# TODO uncomment this code and fix the todos. Note! Need to uncomment the imports as well
# # TODO Update entry annotation
# async def async_setup_entry(
#     hass: HomeAssistant, entry: OpenStreetMapConfigEntry
# ) -> bool:
#     """Set up OpenStreetMap from a config entry."""

#     # TODO 1. Create API instance
#     # TODO 2. Validate the API connection (and authentication)
#     # TODO 3. Store an API object for your platforms to access
#     # entry.runtime_data = MyAPI(...)

#     await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

#     return True


# # TODO Update entry annotation
# async def async_unload_entry(
#     hass: HomeAssistant, entry: OpenStreetMapConfigEntry
# ) -> bool:
#     """Unload a config entry."""
#     return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
