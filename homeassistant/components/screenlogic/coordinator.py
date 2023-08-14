"""ScreenlogicDataUpdateCoordinator definition."""
from datetime import timedelta
import logging

from screenlogicpy import ScreenLogicError, ScreenLogicGateway
from screenlogicpy.const.common import SL_GATEWAY_IP, SL_GATEWAY_NAME, SL_GATEWAY_PORT
from screenlogicpy.device_const.system import EQUIPMENT_FLAG

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .config_flow import async_discover_gateways_by_unique_id, name_for_mac
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

REQUEST_REFRESH_DELAY = 2
HEATER_COOLDOWN_DELAY = 6


async def async_get_connect_info(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, str | int]:
    """Construct connect_info from configuration entry and returns it to caller."""
    mac = entry.unique_id
    # Attempt to rediscover gateway to follow IP changes
    discovered_gateways = await async_discover_gateways_by_unique_id(hass)
    if mac in discovered_gateways:
        return discovered_gateways[mac]

    _LOGGER.warning("Gateway rediscovery failed")
    # Static connection defined or fallback from discovery
    return {
        SL_GATEWAY_NAME: name_for_mac(mac),
        SL_GATEWAY_IP: entry.data[CONF_IP_ADDRESS],
        SL_GATEWAY_PORT: entry.data[CONF_PORT],
    }


class ScreenlogicDataUpdateCoordinator(DataUpdateCoordinator[None]):
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

    async def _async_update_configured_data(self) -> None:
        """Update data sets based on equipment config."""
        if not self.gateway.is_client:
            await self.gateway.async_get_status()
            if EQUIPMENT_FLAG.INTELLICHEM in self.gateway.equipment_flags:
                await self.gateway.async_get_chemistry()

        await self.gateway.async_get_pumps()
        if EQUIPMENT_FLAG.CHLORINATOR in self.gateway.equipment_flags:
            await self.gateway.async_get_scg()

    async def _async_update_data(self) -> None:
        """Fetch data from the Screenlogic gateway."""
        assert self.config_entry is not None
        try:
            if not self.gateway.is_connected:
                connect_info = await async_get_connect_info(
                    self.hass, self.config_entry
                )
                await self.gateway.async_connect(**connect_info)

            await self._async_update_configured_data()
        except ScreenLogicError as ex:
            if self.gateway.is_connected:
                await self.gateway.async_disconnect()
            raise UpdateFailed(ex.msg) from ex
