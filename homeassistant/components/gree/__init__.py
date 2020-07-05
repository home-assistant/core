"""The Gree Climate integration."""
import asyncio
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv

from .bridge import CannotConnect, DeviceHelper
from .const import CONF_DISCOVERY, CONF_STATIC, DEFAULT_DISCOVERY, DOMAIN

_LOGGER = logging.getLogger(__name__)


def ensure_unique_hosts(value):
    """Validate that all configs have a unique host."""
    vol.Schema(vol.Unique("duplicate host entries found"))(
        [DeviceHelper.get_ip(entry[CONF_HOST]) for entry in value]
    )
    return value


GREE_HOST_SCHEMA = vol.Schema({vol.Required(CONF_HOST): cv.string})
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_STATIC, default=[]): vol.All(
                    cv.ensure_list, [GREE_HOST_SCHEMA], ensure_unique_hosts
                ),
                vol.Optional(CONF_DISCOVERY, default=DEFAULT_DISCOVERY): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Gree Climate component."""
    hass.data[DOMAIN] = {"config": config.get(DOMAIN, {}), "devices": {}, "pending": {}}

    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Gree Climate from a config entry."""
    config = hass.data[DOMAIN].get("config")
    static_conf = await asyncio.gather(
        *[
            hass.async_add_executor_job(DeviceHelper.get_ip, host)
            for host in config.get(CONF_STATIC, [])
        ]
    )

    device_infos = []
    devices = []

    # First we'll grab as many devices as we can find on the network
    # it's necessary to bind static devices anyway
    _LOGGER.debug("Scanning network for Gree devices...")

    try:
        for device_info in await DeviceHelper.find_devices():
            device_infos.append(device_info)
    except Exception as exception:  # pylint: disable=broad-except
        raise ConfigEntryNotReady from exception

    for device_info in device_infos:
        if (
            config.get(CONF_DISCOVERY, DEFAULT_DISCOVERY)
            or device_info.ip in static_conf
        ):
            try:
                device = await DeviceHelper.try_bind_device(device_info)
                devices.append(device)

                if device_info.ip in static_conf:
                    static_conf.remove(device_info.ip)
            except CannotConnect:
                _LOGGER.error("Unable to bind to gree device: %s", str(device_info))
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception(
                    "Unexpected error trying to bind to gree device: %s",
                    str(device_info),
                )

    # Anything left over wasn't matched
    for ip_address in static_conf:
        _LOGGER.warning("Unable to find gree device with IP addredd %s", ip_address)

    for device in devices:
        _LOGGER.debug(
            "Adding Gree device at %s:%i (%s)",
            device.device_info.ip,
            device.device_info.port,
            device.device_info.name,
        )

    hass.data[DOMAIN]["devices"] = devices
    hass.data[DOMAIN]["pending"] = devices
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, CLIMATE_DOMAIN)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_forward_entry_unload(
        entry, CLIMATE_DOMAIN
    )

    if unload_ok:
        if "devices" in hass.data[DOMAIN]:
            hass.data[DOMAIN].pop("devices")
        if "pending" in hass.data[DOMAIN]:
            hass.data[DOMAIN].pop("pending")

    return unload_ok
