"""The Screenlogic integration."""
import asyncio
from datetime import timedelta
import logging

from screenlogicpy import ScreenLogicError, ScreenLogicGateway
from screenlogicpy.const import (
    EQUIPMENT,
    SL_GATEWAY_IP,
    SL_GATEWAY_NAME,
    SL_GATEWAY_PORT,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .config_flow import async_discover_gateways_by_unique_id, name_for_mac
from .const import DEFAULT_SCAN_INTERVAL, DISCOVERED_GATEWAYS, DOMAIN
from .services import async_load_screenlogic_services, async_unload_screenlogic_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["switch", "sensor", "binary_sensor", "climate"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Screenlogic component."""
    domain_data = hass.data[DOMAIN] = {}
    domain_data[DISCOVERED_GATEWAYS] = await async_discover_gateways_by_unique_id(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Screenlogic from a config entry."""

    gateway = await hass.async_add_executor_job(get_new_gateway, hass, entry)

    # The api library uses a shared socket connection and does not handle concurrent
    # requests very well.
    api_lock = asyncio.Lock()

    coordinator = ScreenlogicDataUpdateCoordinator(
        hass, config_entry=entry, gateway=gateway, api_lock=api_lock
    )

    async_load_screenlogic_services(hass)

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "listener": entry.add_update_listener(async_update_listener),
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    hass.data[DOMAIN][entry.entry_id]["listener"]()
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    async_unload_screenlogic_services(hass)

    return unload_ok


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


def get_connect_info(hass: HomeAssistant, entry: ConfigEntry):
    """Construct connect_info from configuration entry and returns it to caller."""
    mac = entry.unique_id
    # Attempt to re-discover named gateway to follow IP changes
    discovered_gateways = hass.data[DOMAIN][DISCOVERED_GATEWAYS]
    if mac in discovered_gateways:
        connect_info = discovered_gateways[mac]
    else:
        _LOGGER.warning("Gateway rediscovery failed")
        # Static connection defined or fallback from discovery
        connect_info = {
            SL_GATEWAY_NAME: name_for_mac(mac),
            SL_GATEWAY_IP: entry.data[CONF_IP_ADDRESS],
            SL_GATEWAY_PORT: entry.data[CONF_PORT],
        }

    return connect_info


def get_new_gateway(hass: HomeAssistant, entry: ConfigEntry):
    """Instantiate a new ScreenLogicGateway, connect to it and return it to caller."""

    connect_info = get_connect_info(hass, entry)

    try:
        gateway = ScreenLogicGateway(**connect_info)
    except ScreenLogicError as ex:
        _LOGGER.error("Error while connecting to the gateway %s: %s", connect_info, ex)
        raise ConfigEntryNotReady from ex

    return gateway


class ScreenlogicDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage the data update for the Screenlogic component."""

    def __init__(self, hass, *, config_entry, gateway, api_lock):
        """Initialize the Screenlogic Data Update Coordinator."""
        self.config_entry = config_entry
        self.gateway = gateway
        self.api_lock = api_lock
        self.screenlogic_data = {}

        interval = timedelta(
            seconds=config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=interval,
        )

    def reconnect_gateway(self):
        """Instantiate a new ScreenLogicGateway, connect to it and update. Return new gateway to caller."""

        connect_info = get_connect_info(self.hass, self.config_entry)

        try:
            gateway = ScreenLogicGateway(**connect_info)
            gateway.update()
        except ScreenLogicError as error:
            raise UpdateFailed(error) from error

        return gateway

    async def _async_update_data(self):
        """Fetch data from the Screenlogic gateway."""
        try:
            async with self.api_lock:
                await self.hass.async_add_executor_job(self.gateway.update)
        except ScreenLogicError as error:
            _LOGGER.warning("ScreenLogicError - attempting reconnect: %s", error)

            async with self.api_lock:
                self.gateway = await self.hass.async_add_executor_job(
                    self.reconnect_gateway
                )

        return self.gateway.get_data()


class ScreenlogicEntity(CoordinatorEntity):
    """Base class for all ScreenLogic entities."""

    def __init__(self, coordinator, data_key, enabled=True):
        """Initialize of the entity."""
        super().__init__(coordinator)
        self._data_key = data_key
        self._enabled_default = enabled

    @property
    def entity_registry_enabled_default(self):
        """Entity enabled by default."""
        return self._enabled_default

    @property
    def mac(self):
        """Mac address."""
        return self.coordinator.config_entry.unique_id

    @property
    def unique_id(self):
        """Entity Unique ID."""
        return f"{self.mac}_{self._data_key}"

    @property
    def config_data(self):
        """Shortcut for config data."""
        return self.coordinator.data["config"]

    @property
    def gateway(self):
        """Return the gateway."""
        return self.coordinator.gateway

    @property
    def gateway_name(self):
        """Return the configured name of the gateway."""
        return self.gateway.name

    @property
    def device_info(self):
        """Return device information for the controller."""
        controller_type = self.config_data["controller_type"]
        hardware_type = self.config_data["hardware_type"]
        try:
            equipment_model = EQUIPMENT.CONTROLLER_HARDWARE[controller_type][
                hardware_type
            ]
        except KeyError:
            equipment_model = f"Unknown Model C:{controller_type} H:{hardware_type}"
        return {
            "connections": {(dr.CONNECTION_NETWORK_MAC, self.mac)},
            "name": self.gateway_name,
            "manufacturer": "Pentair",
            "model": equipment_model,
        }
