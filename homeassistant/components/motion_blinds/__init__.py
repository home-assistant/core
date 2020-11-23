"""The motion_blinds component."""
from asyncio import TimeoutError as AsyncioTimeoutError
from datetime import timedelta
import logging
from socket import timeout

from homeassistant import config_entries, core
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, KEY_COORDINATOR, KEY_GATEWAY, MANUFACTURER
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

    def update_gateway():
        """Call all updates using one async_add_executor_job."""
        motion_gateway.Update()
        for blind in motion_gateway.device_list.values():
            blind.Update()

    async def async_update_data():
        """Fetch data from the gateway and blinds."""
        try:
            await hass.async_add_executor_job(update_gateway)
        except timeout as socket_timeout:
            raise AsyncioTimeoutError from socket_timeout

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name=entry.title,
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=10),
    )

    # Fetch initial data so we have data when entities subscribe
    await coordinator.async_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        KEY_GATEWAY: motion_gateway,
        KEY_COORDINATOR: coordinator,
    }

    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, motion_gateway.mac)},
        identifiers={(DOMAIN, entry.unique_id)},
        manufacturer=MANUFACTURER,
        name=entry.title,
        model="Wi-Fi bridge",
        sw_version=motion_gateway.protocol,
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
