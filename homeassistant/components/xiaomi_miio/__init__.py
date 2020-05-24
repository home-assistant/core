"""Support for Xiaomi Miio."""
import logging

from homeassistant import config_entries, core
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.helpers import device_registry as dr

from .config_flow import CONF_FLOW_TYPE, CONF_GATEWAY
from .const import DOMAIN
from .gateway import ConnectXiaomiGateway

_LOGGER = logging.getLogger(__name__)

GATEWAY_PLATFORMS = ["alarm_control_panel"]


async def async_setup(hass: core.HomeAssistant, config: dict):
    """Set up the Xiaomi Miio component."""
    return True


async def async_setup_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
):
    """Set up the Xiaomi Miio components from a config entry."""
    hass.data[DOMAIN] = {}
    if entry.data[CONF_FLOW_TYPE] == CONF_GATEWAY:
        if not await async_setup_gateway_entry(hass, entry):
            return False

    return True


async def async_setup_gateway_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
):
    """Set up the Xiaomi Gateway component from a config entry."""
    host = entry.data[CONF_HOST]
    token = entry.data[CONF_TOKEN]
    name = entry.title
    gateway_id = entry.unique_id

    # For backwards compat
    if entry.unique_id.endswith("-gateway"):
        hass.config_entries.async_update_entry(entry, unique_id=entry.data["mac"])

    # Connect to gateway
    gateway = ConnectXiaomiGateway(hass)
    if not await gateway.async_connect_gateway(host, token):
        return False
    gateway_info = gateway.gateway_info

    hass.data[DOMAIN][entry.entry_id] = gateway.gateway_device

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
