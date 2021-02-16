"""Support for Xiaomi Miio."""
from datetime import timedelta
import logging

from miio.gateway import GatewayException

from homeassistant import config_entries, core
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_DEVICE,
    CONF_FLOW_TYPE,
    CONF_GATEWAY,
    CONF_MODEL,
    DOMAIN,
    KEY_COORDINATOR,
    MODELS_SWITCH,
)
from .gateway import ConnectXiaomiGateway

_LOGGER = logging.getLogger(__name__)

GATEWAY_PLATFORMS = ["alarm_control_panel", "sensor", "light"]
SWITCH_PLATFORMS = ["switch"]


async def async_setup(hass: core.HomeAssistant, config: dict):
    """Set up the Xiaomi Miio component."""
    return True


async def async_setup_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
):
    """Set up the Xiaomi Miio components from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    if entry.data[CONF_FLOW_TYPE] == CONF_GATEWAY:
        if not await async_setup_gateway_entry(hass, entry):
            return False
    if entry.data[CONF_FLOW_TYPE] == CONF_DEVICE:
        if not await async_setup_device_entry(hass, entry):
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

    async def async_update_data():
        """Fetch data from the subdevice."""
        try:
            for sub_device in gateway.gateway_device.devices.values():
                await hass.async_add_executor_job(sub_device.update)
        except GatewayException as ex:
            raise UpdateFailed("Got exception while fetching the state") from ex

    # Create update coordinator
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name=name,
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=10),
    )

    hass.data[DOMAIN][entry.entry_id] = {
        CONF_GATEWAY: gateway.gateway_device,
        KEY_COORDINATOR: coordinator,
    }

    for component in GATEWAY_PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_setup_device_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
):
    """Set up the Xiaomi Miio device component from a config entry."""
    model = entry.data[CONF_MODEL]

    # Identify platforms to setup
    if model in MODELS_SWITCH:
        platforms = SWITCH_PLATFORMS
    else:
        return False

    for component in platforms:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True
