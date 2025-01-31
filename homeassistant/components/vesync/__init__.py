"""VeSync integration."""

import logging

from pyvesync import VeSync

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    EVENT_LOGGING_CHANGED,
    Platform,
)
from homeassistant.core import Event, HomeAssistant, ServiceCall, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .common import async_generate_device_list
from .const import (
    DOMAIN,
    SERVICE_UPDATE_DEVS,
    VS_COORDINATOR,
    VS_DEVICES,
    VS_DISCOVERY,
    VS_LISTENERS,
    VS_MANAGER,
)
from .coordinator import VeSyncDataCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.FAN,
    Platform.HUMIDIFIER,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Vesync as config entry."""
    username = config_entry.data[CONF_USERNAME]
    password = config_entry.data[CONF_PASSWORD]

    time_zone = str(hass.config.time_zone)

    manager = VeSync(
        username=username,
        password=password,
        time_zone=time_zone,
        debug=logging.getLogger("pyvesync.vesync").level == logging.DEBUG,
        redact=True,
    )

    login = await hass.async_add_executor_job(manager.login)

    if not login:
        _LOGGER.error("Unable to login to the VeSync server")
        return False

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][VS_MANAGER] = manager

    coordinator = VeSyncDataCoordinator(hass, manager)

    # Store coordinator at domain level since only single integration instance is permitted.
    hass.data[DOMAIN][VS_COORDINATOR] = coordinator

    hass.data[DOMAIN][VS_DEVICES] = await async_generate_device_list(hass, manager)

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    @callback
    def _async_handle_logging_changed(_event: Event) -> None:
        """Handle when the logging level changes."""
        manager.debug = logging.getLogger("pyvesync.vesync").level == logging.DEBUG

    cleanup = hass.bus.async_listen(
        EVENT_LOGGING_CHANGED, _async_handle_logging_changed
    )

    hass.data[DOMAIN][VS_LISTENERS] = cleanup

    async def async_new_device_discovery(service: ServiceCall) -> None:
        """Discover if new devices should be added."""
        manager = hass.data[DOMAIN][VS_MANAGER]
        devices = hass.data[DOMAIN][VS_DEVICES]

        new_devices = await async_generate_device_list(hass, manager)

        device_set = set(new_devices)
        new_devices = list(device_set.difference(devices))
        if new_devices and devices:
            devices.extend(new_devices)
            async_dispatcher_send(hass, VS_DISCOVERY.format(VS_DEVICES), new_devices)
            return
        if new_devices and not devices:
            devices.extend(new_devices)

    hass.services.async_register(
        DOMAIN, SERVICE_UPDATE_DEVS, async_new_device_discovery
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data[DOMAIN][VS_LISTENERS]()
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.pop(DOMAIN)

    return unload_ok
