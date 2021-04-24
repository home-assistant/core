"""The Overkiz integration."""
import asyncio
from collections import defaultdict
from datetime import timedelta
from enum import Enum
import logging

from aiohttp import ClientError, ServerDisconnectedError
from pyhoma.client import TahomaClient
from pyhoma.exceptions import (
    BadCredentialsException,
    MaintenanceException,
    TooManyRequestsException,
)

from homeassistant.components.scene import DOMAIN as SCENE
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_HUB,
    CONF_UPDATE_INTERVAL,
    DEFAULT_HUB,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    HUB_MANUFACTURER,
    IGNORED_OVERKIZ_DEVICES,
    OVERKIZ_DEVICE_TO_PLATFORM,
    SUPPORTED_ENDPOINTS,
)
from .coordinator import OverkizDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Overkiz from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)
    hub = entry.data.get(CONF_HUB, DEFAULT_HUB)
    endpoint = SUPPORTED_ENDPOINTS[hub]

    session = async_get_clientsession(hass)
    client = TahomaClient(
        username,
        password,
        session=session,
        api_url=endpoint,
    )

    try:
        await client.login()

        tasks = [
            client.get_devices(),
            client.get_scenarios(),
            client.get_gateways(),
            client.get_places(),
        ]
        devices, scenarios, gateways, places = await asyncio.gather(*tasks)
    except BadCredentialsException as exception:
        raise ConfigEntryAuthFailed from exception
    except TooManyRequestsException as exception:
        raise ConfigEntryNotReady("Too many requests, try again later") from exception
    except (TimeoutError, ClientError, ServerDisconnectedError) as exception:
        raise ConfigEntryNotReady("Failed to connect") from exception
    except MaintenanceException as exception:
        raise ConfigEntryNotReady("Server is down for maintenance") from exception
    except Exception as exception:  # pylint: disable=broad-except
        _LOGGER.exception(exception)
        return False

    update_interval = timedelta(
        seconds=entry.options.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
    )

    overkiz_coordinator = OverkizDataUpdateCoordinator(
        hass,
        _LOGGER,
        name="device events",
        client=client,
        devices=devices,
        places=places,
        update_interval=update_interval,
    )

    _LOGGER.debug(
        "Initialized DataUpdateCoordinator with %s interval", str(update_interval)
    )

    await overkiz_coordinator.async_refresh()

    platforms = defaultdict(list)
    platforms[SCENE] = scenarios

    hass.data[DOMAIN][entry.entry_id] = {
        "platforms": platforms,
        "coordinator": overkiz_coordinator,
        "update_listener": entry.add_update_listener(update_listener),
    }

    for device in overkiz_coordinator.data.values():
        platform = OVERKIZ_DEVICE_TO_PLATFORM.get(
            device.widget
        ) or OVERKIZ_DEVICE_TO_PLATFORM.get(device.ui_class)

        if platform:
            platforms[platform].append(device)
            _LOGGER.debug(
                "Added device (%s - %s - %s - %s)",
                device.controllable_name,
                device.ui_class,
                device.widget,
                device.deviceurl,
            )
        elif (
            device.widget not in IGNORED_OVERKIZ_DEVICES
            and device.ui_class not in IGNORED_OVERKIZ_DEVICES
        ):
            _LOGGER.debug(
                "Unsupported Overkiz device detected (%s - %s - %s - %s)",
                device.controllable_name,
                device.ui_class,
                device.widget,
                device.deviceurl,
            )

    for platform in platforms:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    device_registry = dr.async_get(hass)

    for gateway in gateways:
        _LOGGER.debug(
            "Added gateway (%s - %s - %s)",
            gateway.id,
            gateway.type,
            gateway.sub_type,
        )

        if isinstance(gateway.type, Enum):
            gateway_name = f"{beautify_name(gateway.type.name)} hub"
        else:
            gateway_name = gateway.type

        if isinstance(gateway.sub_type, Enum):
            gateway_model = beautify_name(gateway.sub_type.name)
        else:
            gateway_model = None

        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, gateway.id)},
            model=gateway_model,
            manufacturer=HUB_MANUFACTURER[hub],
            name=gateway_name,
            sw_version=gateway.connectivity.protocol_version,
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


def beautify_name(name: str):
    """Return human readable string."""
    return name.replace("_", " ").title()
