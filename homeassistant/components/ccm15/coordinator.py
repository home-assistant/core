"""Climate device for CCM15 coordinator."""
import datetime
import logging

from ccm15 import CCM15Device, CCM15DeviceState, CCM15SlaveDevice
import httpx

from homeassistant.components.climate import HVACMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONST_FAN_CMD_MAP,
    CONST_STATE_CMD_MAP,
    DEFAULT_INTERVAL,
    DEFAULT_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


class CCM15Coordinator(DataUpdateCoordinator[CCM15DeviceState]):
    """Class to coordinate multiple CCM15Climate devices."""

    def __init__(self, hass: HomeAssistant, host: str, port: int) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=host,
            update_interval=datetime.timedelta(seconds=DEFAULT_INTERVAL),
        )
        self._ccm15 = CCM15Device(host, port, DEFAULT_TIMEOUT)
        self._host = host

    def get_host(self) -> str:
        """Get the host."""
        return self._host

    async def _async_update_data(self) -> CCM15DeviceState:
        """Fetch data from Rain Bird device."""
        try:
            return await self._fetch_data()
        except httpx.RequestError as err:  # pragma: no cover
            raise UpdateFailed("Error communicating with Device") from err

    async def _fetch_data(self) -> CCM15DeviceState:
        """Get the current status of all AC devices."""
        return await self._ccm15.get_status_async()

    async def async_set_state(self, ac_index: int, state: str, value: int) -> None:
        """Set new target states."""
        if await self._ccm15.async_set_state(ac_index, state, value):
            await self.async_request_refresh()

    def get_ac_data(self, ac_index: int) -> CCM15SlaveDevice | None:
        """Get ac data from the ac_index."""
        if ac_index < 0 or ac_index >= len(self.data.devices):
            # Network latency may return an empty or incomplete array
            return None
        return self.data.devices[ac_index]

    async def async_set_hvac_mode(self, ac_index, hvac_mode: HVACMode) -> None:
        """Set the hvac mode."""
        _LOGGER.debug("Set Hvac[%s]='%s'", ac_index, str(hvac_mode))
        await self.async_set_state(ac_index, "mode", CONST_STATE_CMD_MAP[hvac_mode])

    async def async_set_fan_mode(self, ac_index, fan_mode: str) -> None:
        """Set the fan mode."""
        _LOGGER.debug("Set Fan[%s]='%s'", ac_index, fan_mode)
        await self.async_set_state(ac_index, "fan", CONST_FAN_CMD_MAP[fan_mode])

    async def async_set_temperature(self, ac_index, temp) -> None:
        """Set the target temperature mode."""
        _LOGGER.debug("Set Temp[%s]='%s'", ac_index, temp)
        await self.async_set_state(ac_index, "temp", temp)
