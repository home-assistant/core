"""Support for Xiaomi Miio."""
import logging

from miio import DeviceException, gateway

from homeassistant import config_entries, core
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

GATEWAY_PLATFORMS = ["alarm_control_panel"]


async def async_setup(hass: core.HomeAssistant, config: dict):
    """Set up the Xiaomi Miio component."""
    return True


async def async_setup_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
):
    """Set up the Xiaomi Miio component from a config entry."""
    host = entry.data[CONF_HOST]
    token = entry.data[CONF_TOKEN]
    name = entry.title
    gateway_id = entry.data["gateway_id"]
    _LOGGER.debug("Initializing with host %s (token %s...)", host, token[:5])

    # Connect to gateway
    try:
        gateway_device = gateway.Gateway(host, token)
        gateway_info = gateway_device.info()
        _LOGGER.debug(
            "%s %s %s detected",
            gateway_info.model,
            gateway_info.firmware_version,
            gateway_info.hardware_version,
        )
    except DeviceException:
        _LOGGER.error(
            "DeviceException during setup of xiaomi gateway with host %s", host
        )
        return False

    hass.data[DOMAIN][entry.entry_id] = gateway_device

    gateway_model = f"{gateway_info.model}-{gateway_info.hardware_version}"

    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, gateway_info.mac_address)},
        identifiers={(DOMAIN, gateway_id)},
        manufacturer="Xiaomi",
        name=name,
        model=gateway_model,
        sw_version=gateway_info.firmware_version,
    )

    for component in GATEWAY_PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True
