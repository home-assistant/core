"""GCE Eco-Devices integration."""
import asyncio
from datetime import timedelta
import logging

from pyecodevices import (
    EcoDevices,
    EcoDevicesCannotConnectError,
    EcoDevicesInvalidAuthError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONFIG,
    CONTROLLER,
    COORDINATOR,
    DOMAIN,
    PLATFORMS,
    UNDO_UPDATE_LISTENER,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Eco-Devices integration."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Eco-Devices from a config entry."""
    config = entry.data

    session = async_get_clientsession(hass, False)

    controller = EcoDevices(
        config.get(CONF_HOST),
        config.get(CONF_PORT),
        config.get(CONF_USERNAME),
        config.get(CONF_PASSWORD),
        session=session,
    )

    try:
        await controller.get_info()
    except EcoDevicesCannotConnectError as exception:
        raise ConfigEntryNotReady from exception

    async def async_update_data():
        """Fetch data from API."""
        try:
            return await controller.global_get()
        except EcoDevicesInvalidAuthError as err:
            raise UpdateFailed("Authentication error on Eco-Devices") from err
        except EcoDevicesCannotConnectError as err:
            raise UpdateFailed(f"Failed to communicating with API: {err}") from err

    scan_interval = config[CONF_SCAN_INTERVAL]

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=async_update_data,
        update_interval=timedelta(seconds=scan_interval),
    )

    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    undo_listener = entry.add_update_listener(_async_update_listener)

    hass.data[DOMAIN][entry.entry_id] = {
        CONTROLLER: controller,
        COORDINATOR: coordinator,
        CONFIG: config,
        UNDO_UPDATE_LISTENER: undo_listener,
    }

    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, controller.host)},
        manufacturer="GCE",
        model="Eco-Devices",
        name=controller.host,
        sw_version=controller.version,
        connections={(dr.CONNECTION_NETWORK_MAC, controller.mac_address)},
    )

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *(
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            )
        )
    )

    hass.data[DOMAIN][entry.entry_id][UNDO_UPDATE_LISTENER]()

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
