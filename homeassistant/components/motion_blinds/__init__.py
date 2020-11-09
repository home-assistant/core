"""The motion_blinds component."""
import logging

from homeassistant import config_entries, core
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, MANUFACTURER
from .gateway import ConnectMotionGateway

_LOGGER = logging.getLogger(__name__)

MOTION_PLATFORMS = ["cover", "sensor"]


async def async_setup(hass: core.HomeAssistant, config: dict):
    """Set up the Motion Blinds component."""
    return True


async def async_setup_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
):
    """Set up the motion_blinds components from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    host = entry.data[CONF_HOST]
    key = entry.data[CONF_API_KEY]

    # Connect to motion gateway
    connect_gateway_class = ConnectMotionGateway(hass)
    if not await connect_gateway_class.async_connect_gateway(host, key):
        raise ConfigEntryNotReady
    motion_gateway = connect_gateway_class.gateway_device

    hass.data[DOMAIN][entry.entry_id] = motion_gateway

    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, motion_gateway.mac)},
        identifiers={(DOMAIN, entry.unique_id)},
        manufacturer=MANUFACTURER,
        name=entry.title,
        model="Wi-Fi bridge",
        sw_version=motion_gateway.protecol,
    )

    for component in MOTION_PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(
    hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry
):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_forward_entry_unload(
        config_entry, "cover"
    )

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok
