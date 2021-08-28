"""The Contec Controllers integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from ContecControllers.ContecConectivityConfiguration import (
    ContecConectivityConfiguration,
)
from ContecControllers.ControllerManager import ControllerManager

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .contec_tracer import ContecTracer

PLATFORMS = ["light"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Contec Controllers from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    numberOfControllers: int = entry.data["numberOfControllers"]
    controllersIp: str = entry.data["ip"]
    controllersPort: int = entry.data["port"]
    controllerManager: ControllerManager = ControllerManager(
        ContecTracer(logging.getLogger("ContecControllers")),
        ContecConectivityConfiguration(
            numberOfControllers,
            controllersIp,
            controllersPort,
        ),
    )

    controllerManager.Init()
    if not await controllerManager.IsConnected(timedelta(seconds=7)):
        _LOGGER.warning(
            f"Failed to connect to Contec Controllers at address {controllersIp},{controllersPort}"
        )
        await controllerManager.CloseAsync()
        raise ConfigEntryNotReady

    await controllerManager.DiscoverEntitiesAsync()

    hass.data[DOMAIN][entry.entry_id] = controllerManager
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    controllerManager: ControllerManager = hass.data[DOMAIN][entry.entry_id]
    if controllerManager is not None:
        await controllerManager.CloseAsync()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
