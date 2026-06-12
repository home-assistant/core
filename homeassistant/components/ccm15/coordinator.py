"""Climate device for CCM15 coordinator."""

from copy import deepcopy
import datetime
import logging

from ccm15 import CCM15Device, CCM15DeviceState, CCM15SlaveDevice
import httpx

from homeassistant.components.climate import HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONST_FAN_CMD_MAP,
    CONST_STATE_CMD_MAP,
    DEFAULT_INTERVAL,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DEFAULT_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

# How long to keep showing a value we just sent before letting the device
# overwrite it. The CCM15 firmware can take several seconds to commit a
# change and the status endpoint reports the pre-change value in the
# meantime, which made the UI snap back.
OPTIMISTIC_WINDOW = datetime.timedelta(seconds=12)

type CCM15ConfigEntry = ConfigEntry[CCM15Coordinator]


class CCM15Coordinator(DataUpdateCoordinator[CCM15DeviceState]):
    """Coordinate multiple CCM15 slave devices behind one controller."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: CCM15ConfigEntry,
        host: str,
        port: int,
        min_temp: int = DEFAULT_MIN_TEMP,
        max_temp: int = DEFAULT_MAX_TEMP,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=host,
            update_interval=datetime.timedelta(seconds=DEFAULT_INTERVAL),
        )
        # Pass HA's shared httpx client into py_ccm15 so the library does
        # not construct its own AsyncClient inside the event loop, which
        # would synchronously load the certifi CA bundle and trip the
        # blocking-call detector.
        self._ccm15 = CCM15Device(
            host, port, DEFAULT_TIMEOUT, client=get_async_client(hass)
        )
        self._host = host
        self._min_temp = min_temp
        self._max_temp = max_temp
        self._optimistic: dict[int, tuple[datetime.datetime, CCM15SlaveDevice]] = {}

    def get_host(self) -> str:
        """Return the controller host."""
        return self._host

    @property
    def min_temp(self) -> int:
        """Return the configured minimum target temperature."""
        return self._min_temp

    @property
    def max_temp(self) -> int:
        """Return the configured maximum target temperature."""
        return self._max_temp

    async def _async_update_data(self) -> CCM15DeviceState:
        """Fetch data from the CCM15 device."""
        try:
            ac_data = await self._ccm15.get_status_async()
        except httpx.RequestError as err:
            raise UpdateFailed(
                f"Error communicating with {self._host}: {type(err).__name__}: {err}"
            ) from err

        now = dt_util.utcnow()
        for idx, (set_at, set_data) in list(self._optimistic.items()):
            if now - set_at > OPTIMISTIC_WINDOW:
                del self._optimistic[idx]
                continue
            if idx in ac_data.devices:
                ac_data.devices[idx] = set_data

        return ac_data

    async def async_set_state(self, ac_index: int, data: CCM15SlaveDevice) -> None:
        """Send a new target state for a slave AC."""
        try:
            ok = await self._ccm15.async_set_state(ac_index, data)
        except httpx.RequestError as err:
            _LOGGER.error(
                "Error sending state to CCM15 (%s): %s: %s",
                self._host,
                type(err).__name__,
                err,
            )
            return
        if ok:
            self._optimistic[ac_index] = (dt_util.utcnow(), deepcopy(data))
            self.async_set_updated_data(self.data)
            await self.async_request_refresh()

    def get_ac_data(self, ac_index: int) -> CCM15SlaveDevice | None:
        """Return the slave device for an index, or None if not present."""
        return self.data.devices.get(ac_index)

    async def async_set_hvac_mode(
        self, ac_index: int, data: CCM15SlaveDevice, hvac_mode: HVACMode
    ) -> None:
        """Set the HVAC mode."""
        data.ac_mode = CONST_STATE_CMD_MAP[hvac_mode]
        await self.async_set_state(ac_index, data)

    async def async_set_fan_mode(
        self, ac_index: int, data: CCM15SlaveDevice, fan_mode: str
    ) -> None:
        """Set the fan mode."""
        data.fan_mode = CONST_FAN_CMD_MAP[fan_mode]
        await self.async_set_state(ac_index, data)

    async def async_set_temperature(
        self,
        ac_index: int,
        data: CCM15SlaveDevice,
        temp: int,
        hvac_mode: HVACMode | None,
    ) -> None:
        """Set the target temperature."""
        data.temperature_setpoint = temp
        if hvac_mode is not None:
            data.ac_mode = CONST_STATE_CMD_MAP[hvac_mode]
        await self.async_set_state(ac_index, data)
