"""The Screenlogic integration."""
from datetime import timedelta
import logging
from typing import Any

from screenlogicpy import ScreenLogicError, ScreenLogicGateway
from screenlogicpy.const import (
    DATA as SL_DATA,
    EQUIPMENT,
    SL_GATEWAY_IP,
    SL_GATEWAY_NAME,
    SL_GATEWAY_PORT,
    ScreenLogicWarning,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT, CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .config_flow import async_discover_gateways_by_unique_id, name_for_mac
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .services import async_load_screenlogic_services, async_unload_screenlogic_services

_LOGGER = logging.getLogger(__name__)


REQUEST_REFRESH_DELAY = 2
HEATER_COOLDOWN_DELAY = 6

# These seem to be constant across all controller models
PRIMARY_CIRCUIT_IDS = [500, 505]  # [Spa, Pool]

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Screenlogic from a config entry."""
    gateway = ScreenLogicGateway()

    connect_info = await async_get_connect_info(hass, entry)

    try:
        await gateway.async_connect(**connect_info)
    except ScreenLogicError as ex:
        _LOGGER.error("Error while connecting to the gateway %s: %s", connect_info, ex)
        raise ConfigEntryNotReady from ex

    coordinator = ScreenlogicDataUpdateCoordinator(
        hass, config_entry=entry, gateway=gateway
    )

    async_load_screenlogic_services(hass)

    await coordinator.async_config_entry_first_refresh()

    entry.async_on_unload(entry.add_update_listener(async_update_listener))

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.gateway.async_disconnect()
        hass.data[DOMAIN].pop(entry.entry_id)

    async_unload_screenlogic_services(hass)

    return unload_ok


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_get_connect_info(hass: HomeAssistant, entry: ConfigEntry):
    """Construct connect_info from configuration entry and returns it to caller."""
    mac = entry.unique_id
    # Attempt to rediscover gateway to follow IP changes
    discovered_gateways = await async_discover_gateways_by_unique_id(hass)
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


class ScreenlogicDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage the data update for the Screenlogic component."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        config_entry: ConfigEntry,
        gateway: ScreenLogicGateway,
    ) -> None:
        """Initialize the Screenlogic Data Update Coordinator."""
        self.config_entry = config_entry
        self.gateway = gateway

        interval = timedelta(
            seconds=config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=interval,
            # Debounced option since the device takes
            # a moment to reflect the knock-on changes
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=REQUEST_REFRESH_DELAY, immediate=False
            ),
        )

    @property
    def gateway_data(self) -> dict[str | int, Any]:
        """Return the gateway data."""
        return self.gateway.get_data()

    async def _async_update_configured_data(self):
        """Update data sets based on equipment config."""
        equipment_flags = self.gateway.get_data()[SL_DATA.KEY_CONFIG]["equipment_flags"]
        if not self.gateway.is_client:
            await self.gateway.async_get_status()
            if equipment_flags & EQUIPMENT.FLAG_INTELLICHEM:
                await self.gateway.async_get_chemistry()

        await self.gateway.async_get_pumps()
        if equipment_flags & EQUIPMENT.FLAG_CHLORINATOR:
            await self.gateway.async_get_scg()

    async def _async_update_data(self):
        """Fetch data from the Screenlogic gateway."""
        try:
            await self._async_update_configured_data()
        except ScreenLogicError as error:
            _LOGGER.warning("Update error - attempting reconnect: %s", error)
            await self._async_reconnect_update_data()
        except ScreenLogicWarning as warn:
            raise UpdateFailed(f"Incomplete update: {warn}") from warn

        return None

    async def _async_reconnect_update_data(self):
        """Attempt to reconnect to the gateway and fetch data."""
        try:
            # Clean up the previous connection as we're about to create a new one
            await self.gateway.async_disconnect()

            connect_info = await async_get_connect_info(self.hass, self.config_entry)
            await self.gateway.async_connect(**connect_info)

            await self._async_update_configured_data()

        except (ScreenLogicError, ScreenLogicWarning) as ex:
            raise UpdateFailed(ex) from ex
