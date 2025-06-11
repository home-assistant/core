"""VeSync integration."""

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .common import async_generate_device_list
from .const import DOMAIN, SERVICE_UPDATE_DEVS, VS_DEVICES, VS_DISCOVERY, VS_MANAGER


async def _async_new_device_discovery(service: ServiceCall) -> None:
    """Discover if new devices should be added."""
    hass = service.hass
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


def async_setup_services(hass: HomeAssistant) -> None:
    """Register integration services."""
    hass.services.async_register(
        DOMAIN, SERVICE_UPDATE_DEVS, _async_new_device_discovery
    )
