"""Climate device for CCM15 coordinator."""

from copy import deepcopy
import datetime
import logging

from ccm15 import CCM15DeviceState, CCM15SlaveDevice
import httpx
import xmltodict

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

URL_STATUS = "status.xml"
URL_CTRL = "ctrl.xml"

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
        password: str | None = None,
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
        self._host = host
        self._port = port
        self._password = password
        self._min_temp = min_temp
        self._max_temp = max_temp
        self._timeout = DEFAULT_TIMEOUT
        self._client = get_async_client(hass)
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
        """Fetch device state."""
        try:
            return await self._fetch_data()
        except httpx.RequestError as err:
            raise UpdateFailed("Error communicating with Device") from err

    async def _fetch_data(self) -> CCM15DeviceState:
        """Read status.xml and decode each slave device."""
        url = f"http://{self._host}:{self._port}/{URL_STATUS}"
        response = await self._client.get(url, timeout=self._timeout)
        doc = xmltodict.parse(response.text)
        data = doc["response"]
        ac_data = CCM15DeviceState(devices={})
        ac_index = 0
        for ac_binary in data.values():
            # Empty slots in the middle of the array are possible; skip
            # them instead of stopping the scan, which is what the old
            # code did on the first "-" entry.
            if ac_binary is None or ac_binary == "-":
                ac_index += 1
                continue
            try:
                bytesarr = bytes.fromhex(ac_binary.strip(","))
            except AttributeError, ValueError:
                ac_index += 1
                continue
            ac_data.devices[ac_index] = CCM15SlaveDevice(bytesarr)
            ac_index += 1

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
        ac_id = 2**ac_index
        pwd_part = f"pwd={self._password}&" if self._password else ""
        sw = 1 if data.is_swing_on else 0
        url = (
            f"http://{self._host}:{self._port}/{URL_CTRL}"
            f"?{pwd_part}ac0={ac_id}&ac1=0"
            f"&mode={data.ac_mode}"
            f"&fan={data.fan_mode}"
            f"&temp={data.temperature_setpoint}"
            f"&sw={sw}"
            f"&ht=0"
        )
        try:
            response = await self._client.get(url, timeout=self._timeout)
        except httpx.RequestError as err:
            _LOGGER.error("Error sending state to CCM15: %s", err)
            return
        if response.status_code in (httpx.codes.OK, httpx.codes.FOUND):
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

    async def async_set_swing_mode(
        self, ac_index: int, data: CCM15SlaveDevice, swing_on: bool
    ) -> None:
        """Set the swing mode."""
        data.is_swing_on = swing_on
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
