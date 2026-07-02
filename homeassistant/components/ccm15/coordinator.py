"""Climate device for CCM15 coordinator."""

import datetime
import logging
from typing import override

from ccm15 import (
    CCM15Device,
    CCM15DeviceState,
    CCM15ReturnCode,
    CCM15SlaveDevice,
    TriState,
)
import httpx

from homeassistant.components.climate import SWING_ON, HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONST_FAN_CMD_MAP,
    CONST_STATE_CMD_MAP,
    DEFAULT_INTERVAL,
    DEFAULT_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

type CCM15ConfigEntry = ConfigEntry[CCM15Coordinator]


class CCM15Coordinator(DataUpdateCoordinator[CCM15DeviceState]):
    """Class to coordinate multiple CCM15Climate devices."""

    def __init__(
        self, hass: HomeAssistant, entry: CCM15ConfigEntry, host: str, port: int
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=host,
            update_interval=datetime.timedelta(seconds=DEFAULT_INTERVAL),
        )
        self._ccm15 = CCM15Device(
            host, port, DEFAULT_TIMEOUT, client=get_async_client(hass)
        )
        self._host = host

    def get_host(self) -> str:
        """Get the host."""
        return self._host

    @override
    async def _async_update_data(self) -> CCM15DeviceState:
        """Fetch data from the CCM15 device."""
        try:
            return await self._fetch_data()
        except httpx.RequestError as err:
            raise UpdateFailed("Error communicating with Device") from err

    async def _fetch_data(self) -> CCM15DeviceState:
        """Get the current status of all AC devices."""
        return await self._ccm15.get_status_async()

    async def async_set_state(self, ac_index: int, data) -> None:
        """Set new target states."""
        if await self._ccm15.async_set_state(ac_index, data) is CCM15ReturnCode.OK:
            await self.async_request_refresh()

    def get_ac_data(self, ac_index: int) -> CCM15SlaveDevice | None:
        """Get ac data from the ac_index."""
        # Slot indices can be sparse and reach >= 32, so look up by key.
        return self.data.devices.get(ac_index)

    async def async_set_hvac_mode(
        self, ac_index: int, data: CCM15SlaveDevice, hvac_mode: HVACMode
    ) -> None:
        """Set the HVAC mode."""
        _LOGGER.debug("Set Hvac[%s]='%s'", ac_index, str(hvac_mode))
        data.ac_mode = CONST_STATE_CMD_MAP[hvac_mode]
        await self.async_set_state(ac_index, data)

    async def async_set_fan_mode(
        self, ac_index: int, data: CCM15SlaveDevice, fan_mode: str
    ) -> None:
        """Set the fan mode."""
        _LOGGER.debug("Set Fan[%s]='%s'", ac_index, fan_mode)
        data.fan_mode = CONST_FAN_CMD_MAP[fan_mode]
        await self.async_set_state(ac_index, data)

    async def async_set_swing_mode(
        self, ac_index: int, data: CCM15SlaveDevice, swing_mode: str
    ) -> None:
        """Set the swing mode."""
        _LOGGER.debug("Set Swing[%s]='%s'", ac_index, swing_mode)
        data.desired_swing = TriState.ON if swing_mode == SWING_ON else TriState.OFF
        await self.async_set_state(ac_index, data)

    async def async_set_temperature(
        self,
        ac_index: int,
        data: CCM15SlaveDevice,
        temp: int,
        hvac_mode: HVACMode | None,
    ) -> None:
        """Set the target temperature mode."""
        _LOGGER.debug("Set Temp[%s]='%s'", ac_index, temp)
        data.temperature_setpoint = temp
        if hvac_mode is not None:
            data.ac_mode = CONST_STATE_CMD_MAP[hvac_mode]
        await self.async_set_state(ac_index, data)
