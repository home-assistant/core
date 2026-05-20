"""Code to set up a device tracker platform using a config entry."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import EntityComponent

from . import (  # noqa: F401
    DATA_COMPONENT,
    BaseTrackerEntity,
    ScannerEntity,
    SourceType,
    TrackerEntity,
    TrackerEntityDescription,
)
from .const import DOMAIN, LOGGER


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up an entry."""
    component: EntityComponent[BaseTrackerEntity] | None = hass.data.get(DOMAIN)

    if component is not None:
        return await component.async_setup_entry(entry)

    component = hass.data[DATA_COMPONENT] = EntityComponent[BaseTrackerEntity](
        LOGGER, DOMAIN, hass
    )
    component.register_shutdown()

    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)
