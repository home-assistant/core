"""Support for Xiaomi Miio."""
from datetime import timedelta
import logging

import async_timeout
from miio import AirHumidifier, AirHumidifierMiot, DeviceException
from miio.gateway.gateway import GatewayException

from homeassistant import config_entries, core
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ATTR_AVAILABLE,
    CONF_DEVICE,
    CONF_FLOW_TYPE,
    CONF_GATEWAY,
    CONF_MODEL,
    DOMAIN,
    KEY_COORDINATOR,
    KEY_DEVICE,
    MODELS_AIR_MONITOR,
    MODELS_FAN,
    MODELS_HUMIDIFIER,
    MODELS_HUMIDIFIER_MIOT,
    MODELS_LIGHT,
    MODELS_SWITCH,
    MODELS_VACUUM,
)
from .gateway import ConnectXiaomiGateway

_LOGGER = logging.getLogger(__name__)

GATEWAY_PLATFORMS = ["alarm_control_panel", "light", "sensor", "switch"]
SWITCH_PLATFORMS = ["switch"]
FAN_PLATFORMS = ["fan"]
HUMIDIFIER_PLATFORMS = ["humidifier", "number", "select", "sensor", "switch"]
LIGHT_PLATFORMS = ["light"]
VACUUM_PLATFORMS = ["vacuum"]
AIR_MONITOR_PLATFORMS = ["air_quality", "sensor"]


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


@callback
def get_platforms(config_entry):
    """Return the platforms belonging to a config_entry."""
    model = config_entry.data[CONF_MODEL]
    flow_type = config_entry.data[CONF_FLOW_TYPE]

    if flow_type == CONF_GATEWAY:
        return GATEWAY_PLATFORMS
    if flow_type == CONF_DEVICE:
        if model in MODELS_SWITCH:
            return SWITCH_PLATFORMS
        if model in MODELS_HUMIDIFIER:
            return HUMIDIFIER_PLATFORMS
        if model in MODELS_FAN:
            return FAN_PLATFORMS
        if model in MODELS_LIGHT:
            return LIGHT_PLATFORMS
        for vacuum_model in MODELS_VACUUM:
            if model.startswith(vacuum_model):
                return VACUUM_PLATFORMS
        for air_monitor_model in MODELS_AIR_MONITOR:
            if model.startswith(air_monitor_model):
                return AIR_MONITOR_PLATFORMS
    _LOGGER.error(
        "Unsupported device found! Please create an issue at "
        "https://github.com/syssi/xiaomi_airpurifier/issues "
        "and provide the following data: %s",
        model,
    )
    return []


async def async_create_miio_device_and_coordinator(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
):
    """Set up a data coordinator and one miio device to service multiple entities."""
    model = entry.data[CONF_MODEL]
    host = entry.data[CONF_HOST]
    token = entry.data[CONF_TOKEN]
    name = entry.title
    device = None

    if model not in MODELS_HUMIDIFIER:
        return

    _LOGGER.debug("Initializing with host %s (token %s...)", host, token[:5])

    if model in MODELS_HUMIDIFIER_MIOT:
        device = AirHumidifierMiot(host, token)
    else:
        device = AirHumidifier(host, token, model=model)

    # Removing fan platform entity for humidifiers and migrate the name to the config entry for migration
    entity_registry = er.async_get(hass)
    entity_id = entity_registry.async_get_entity_id("fan", DOMAIN, entry.unique_id)
    if entity_id:
        # This check is entities that have a platform migration only and should be removed in the future
        if migrate_entity_name := entity_registry.async_get(entity_id).name:
            hass.config_entries.async_update_entry(entry, title=migrate_entity_name)
        entity_registry.async_remove(entity_id)

    async def async_update_data():
        """Fetch data from the device using async_add_executor_job."""
        try:
            async with async_timeout.timeout(10):
                return await hass.async_add_executor_job(device.status)

        except DeviceException as ex:
            raise UpdateFailed(ex) from ex

    # Create update miio device and coordinator
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=name,
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=60),
    )
    hass.data[DOMAIN][entry.entry_id] = {
        KEY_DEVICE: device,
        KEY_COORDINATOR: coordinator,
    }

    # Trigger first data fetch
    await coordinator.async_config_entry_first_refresh()


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

    entry.async_on_unload(entry.add_update_listener(update_listener))

    # Connect to gateway
    gateway = ConnectXiaomiGateway(hass, entry)
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
    platforms = get_platforms(entry)
    await async_create_miio_device_and_coordinator(hass, entry)

    if not platforms:
        return False

    entry.async_on_unload(entry.add_update_listener(update_listener))

    hass.config_entries.async_setup_platforms(entry, platforms)

    return True


async def async_unload_entry(
    hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry
):
    """Unload a config entry."""
    platforms = get_platforms(config_entry)

    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, platforms
    )

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


async def update_listener(
    hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry
):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)
