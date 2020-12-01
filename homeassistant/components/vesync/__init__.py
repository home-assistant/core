"""VeSync integration."""
import asyncio
import logging

from pyvesync import VeSync
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .common import async_process_devices
from .config_flow import configured_instances
from .const import (
    DOMAIN,
    SERVICE_UPDATE_DEVS,
    VS_DISCOVERY,
    VS_DISPATCHERS,
    VS_FANS,
    VS_MANAGER,
    VS_SWITCHES,
)

PLATFORMS = ["switch", "fan"]

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the VeSync component."""
    conf = config.get(DOMAIN)

    if conf is None:
        return True

    if not configured_instances(hass):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data={
                    CONF_USERNAME: conf[CONF_USERNAME],
                    CONF_PASSWORD: conf[CONF_PASSWORD],
                },
            )
        )

    return True


async def async_setup_entry(hass, config_entry):
    """Set up Vesync as config entry."""
    username = config_entry.data[CONF_USERNAME]
    password = config_entry.data[CONF_PASSWORD]

    time_zone = str(hass.config.time_zone)

    manager = VeSync(username, password, time_zone)

    login = await hass.async_add_executor_job(manager.login)

    if not login:
        _LOGGER.error("Unable to login to the VeSync server")
        return False

    device_dict = await async_process_devices(hass, manager)

    forward_setup = hass.config_entries.async_forward_entry_setup

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][VS_MANAGER] = manager

    switches = hass.data[DOMAIN][VS_SWITCHES] = []
    fans = hass.data[DOMAIN][VS_FANS] = []

    hass.data[DOMAIN][VS_DISPATCHERS] = []

    if device_dict[VS_SWITCHES]:
        switches.extend(device_dict[VS_SWITCHES])
        hass.async_create_task(forward_setup(config_entry, "switch"))

    if device_dict[VS_FANS]:
        fans.extend(device_dict[VS_FANS])
        hass.async_create_task(forward_setup(config_entry, "fan"))

    async def async_new_device_discovery(service):
        """Discover if new devices should be added."""
        manager = hass.data[DOMAIN][VS_MANAGER]
        switches = hass.data[DOMAIN][VS_SWITCHES]
        fans = hass.data[DOMAIN][VS_FANS]

        dev_dict = await async_process_devices(hass, manager)
        switch_devs = dev_dict.get(VS_SWITCHES, [])
        fan_devs = dev_dict.get(VS_FANS, [])

        switch_set = set(switch_devs)
        new_switches = list(switch_set.difference(switches))
        if new_switches and switches:
            switches.extend(new_switches)
            async_dispatcher_send(hass, VS_DISCOVERY.format(VS_SWITCHES), new_switches)
            return
        if new_switches and not switches:
            switches.extend(new_switches)
            hass.async_create_task(forward_setup(config_entry, "switch"))

        fan_set = set(fan_devs)
        new_fans = list(fan_set.difference(fans))
        if new_fans and fans:
            fans.extend(new_fans)
            async_dispatcher_send(hass, VS_DISCOVERY.format(VS_FANS), new_fans)
            return
        if new_fans and not fans:
            fans.extend(new_fans)
            hass.async_create_task(forward_setup(config_entry, "fan"))

    hass.services.async_register(
        DOMAIN, SERVICE_UPDATE_DEVS, async_new_device_discovery
    )

    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
