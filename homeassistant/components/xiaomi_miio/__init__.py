"""Support for Xiaomi Miio."""
from datetime import timedelta
import logging

from miio.gateway.gateway import GatewayException

from homeassistant import config_entries, core
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    ATTR_AVAILABLE,
    CONF_DEVICE,
    CONF_FLOW_TYPE,
    CONF_GATEWAY,
    CONF_MODEL,
    DOMAIN,
    KEY_COORDINATOR,
    MODELS_AIR_MONITOR,
    MODELS_FAN,
    MODELS_LIGHT,
    MODELS_SWITCH,
    MODELS_VACUUM,
)
from .gateway import ConnectXiaomiGateway

_LOGGER = logging.getLogger(__name__)

GATEWAY_PLATFORMS = ["alarm_control_panel", "light", "sensor", "switch"]
SWITCH_PLATFORMS = ["switch"]
FAN_PLATFORMS = ["fan"]
LIGHT_PLATFORMS = ["light"]
VACUUM_PLATFORMS = ["vacuum"]
AIR_MONITOR_PLATFORMS = ["air_quality", "sensor"]


async def async_setup(hass: core.HomeAssistant, config: dict):
    """Set up the Xiaomi Miio component."""
    return True


async def async_setup_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
):
    """Set up the Xiaomi Miio components from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    if entry.data[
        CONF_FLOW_TYPE
    ] == CONF_GATEWAY and not await async_setup_gateway_entry(hass, entry):
        return False

    return bool(
        entry.data[CONF_FLOW_TYPE] != CONF_DEVICE
        or await async_setup_device_entry(hass, entry)
    )


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

    def update_data():
        """Fetch data from the subdevice."""
        data = {}
        for sub_device in gateway.gateway_device.devices.values():
            try:
                sub_device.update()
            except GatewayException as ex:
                _LOGGER.error("Got exception while fetching the state: %s", ex)
                data[sub_device.sid] = {ATTR_AVAILABLE: False}
            else:
                data[sub_device.sid] = {ATTR_AVAILABLE: True}
        return data

    async def async_update_data():
        """Fetch data from the subdevice using async_add_executor_job."""
        return await hass.async_add_executor_job(update_data)

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

    for platform in GATEWAY_PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_setup_device_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
):
    """Set up the Xiaomi Miio device component from a config entry."""
    model = entry.data[CONF_MODEL]

    # Identify platforms to setup
    platforms = []
    if model in MODELS_SWITCH:
        platforms = SWITCH_PLATFORMS
    elif model in MODELS_FAN:
        platforms = FAN_PLATFORMS
    elif model in MODELS_LIGHT:
        platforms = LIGHT_PLATFORMS
    for vacuum_model in MODELS_VACUUM:
        if model.startswith(vacuum_model):
            platforms = VACUUM_PLATFORMS
    for air_monitor_model in MODELS_AIR_MONITOR:
        if model.startswith(air_monitor_model):
            platforms = AIR_MONITOR_PLATFORMS

    if not platforms:
        return False

    for platform in platforms:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True
