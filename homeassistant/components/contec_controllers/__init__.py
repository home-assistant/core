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

    number_of_controllers: int = entry.data["number_of_controllers"]
    controllers_ip: str = entry.data["ip"]
    controllers_port: int = entry.data["port"]
    controller_manager: ControllerManager = ControllerManager(
        ContecTracer(logging.getLogger("ContecControllers")),
        ContecConectivityConfiguration(
            number_of_controllers,
            controllers_ip,
            controllers_port,
        ),
    )

    controller_manager.Init()
    if not await controller_manager.IsConnected(timedelta(seconds=7)):
        _LOGGER.warning(
            f"Failed to connect to Contec Controllers at address {controllers_ip},{controllers_port}"
        )
        await controller_manager.CloseAsync()
        raise ConfigEntryNotReady

    await controller_manager.DiscoverEntitiesAsync()

    hass.data[DOMAIN][entry.entry_id] = controller_manager
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    controller_manager: ControllerManager = hass.data[DOMAIN][entry.entry_id]
    if controller_manager is not None:
        await controller_manager.CloseAsync()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
