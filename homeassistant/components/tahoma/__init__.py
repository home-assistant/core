"""The Somfy TaHoma integration."""
import asyncio
from collections import defaultdict
from datetime import timedelta
import logging

from aiohttp import ClientError, ServerDisconnectedError
from pyhoma.client import TahomaClient
from pyhoma.exceptions import (
    BadCredentialsException,
    MaintenanceException,
    TooManyRequestsException,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client

from .const import (
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    IGNORED_TAHOMA_TYPES,
    TAHOMA_TYPES,
)
from .coordinator import TahomaDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Somfy TaHoma component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Somfy TaHoma from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)

    session = aiohttp_client.async_create_clientsession(hass)
    client = TahomaClient(username, password, session=session)

    try:
        await client.login()
        devices = await client.get_devices()
        places = await client.get_places()
    except BadCredentialsException:
        _LOGGER.error("Invalid authentication.")
        return False
    except TooManyRequestsException as exception:
        _LOGGER.error("Too many requests, try again later.")
        raise ConfigEntryNotReady from exception
    except (TimeoutError, ClientError, ServerDisconnectedError) as exception:
        _LOGGER.error("Failed to connect.")
        raise ConfigEntryNotReady from exception
    except MaintenanceException as exception:
        _LOGGER.error("Server is down for maintenance.")
        raise ConfigEntryNotReady from exception
    except Exception as exception:  # pylint: disable=broad-except
        _LOGGER.exception(exception)
        return False

    update_interval = timedelta(
        seconds=entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    )

    tahoma_coordinator = TahomaDataUpdateCoordinator(
        hass,
        _LOGGER,
        name="device events",
        client=client,
        devices=devices,
        places=places,
        update_interval=update_interval,
    )

    _LOGGER.debug(
        "Initialized DataUpdateCoordinator with %s interval.", str(update_interval)
    )

    await tahoma_coordinator.async_refresh()

    platforms = defaultdict(list)

    hass.data[DOMAIN][entry.entry_id] = {
        "platforms": platforms,
        "coordinator": tahoma_coordinator,
        "update_listener": entry.add_update_listener(update_listener),
    }

    for device in tahoma_coordinator.data.values():
        platform = TAHOMA_TYPES.get(device.widget) or TAHOMA_TYPES.get(device.ui_class)
        if platform:
            platforms[platform].append(device)
        elif (
            device.widget not in IGNORED_TAHOMA_TYPES
            and device.ui_class not in IGNORED_TAHOMA_TYPES
        ):
            _LOGGER.debug(
                "Unsupported TaHoma device detected (%s - %s - %s)",
                device.controllable_name,
                device.ui_class,
                device.widget,
            )

    for platform in platforms:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    devices_per_platform = hass.data[DOMAIN][entry.entry_id]["platforms"]

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in devices_per_platform
            ]
        )
    )

    if unload_ok:
        hass.data[DOMAIN][entry.entry_id]["update_listener"]()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Update when config_entry options update."""
    if entry.options[CONF_UPDATE_INTERVAL]:
        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        new_update_interval = timedelta(seconds=entry.options[CONF_UPDATE_INTERVAL])
        coordinator.update_interval = new_update_interval
        coordinator.original_update_interval = new_update_interval

        await coordinator.async_refresh()
