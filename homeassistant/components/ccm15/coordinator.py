"""Climate device for CCM15 coordinator."""
import asyncio
from dataclasses import dataclass
import datetime
import logging

import aiohttp
import httpx
import xmltodict

from homeassistant.components.climate import (
    HVACMode,
)
from homeassistant.const import (
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .climate import CCM15Climate
from .const import (
    BASE_URL,
    CONF_URL_CTRL,
    CONF_URL_STATUS,
    CONST_FAN_CMD_MAP,
    CONST_STATE_CMD_MAP,
    DEFAULT_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class CCM15SlaveDevice:
    """Data retrieved from a CCM15 slave device."""

    def __init__(self, bytesarr: bytes) -> None:
        """Initialize the slave device."""
        self.unit = UnitOfTemperature.CELSIUS
        buf = bytesarr[0]
        if (buf >> 0) & 1:
            self.unit = UnitOfTemperature.FAHRENHEIT
        self.locked_cool_temperature: int = (buf >> 3) & 0x1F

        buf = bytesarr[1]
        self.locked_heat_temperature: int = (buf >> 0) & 0x1F
        self.locked_wind: int = (buf >> 5) & 7

        buf = bytesarr[2]
        self.locked_ac_mode: int = (buf >> 0) & 3
        self.error_code: int = (buf >> 2) & 0x3F

        buf = bytesarr[3]
        self.ac_mode: int = (buf >> 2) & 7
        self.fan_mode: int = (buf >> 5) & 7

        buf = (buf >> 1) & 1
        self.is_ac_mode_locked: bool = buf != 0

        buf = bytesarr[4]
        self.temperature_setpoint: int = (buf >> 3) & 0x1F
        if self.unit == UnitOfTemperature.FAHRENHEIT:
            self.temperature_setpoint += 62
            self.locked_cool_temperature += 62
            self.locked_heat_temperature += 62
        self.is_swing_on: bool = (buf >> 1) & 1 != 0

        buf = bytesarr[5]
        if ((buf >> 3) & 1) == 0:
            self.locked_cool_temperature = 0
        if ((buf >> 4) & 1) == 0:
            self.locked_heat_temperature = 0
        self.fan_locked: bool = buf >> 5 & 1 != 0
        self.is_remote_locked: bool = ((buf >> 6) & 1) != 0

        buf = bytesarr[6]
        self.temperature: int = buf if buf < 128 else buf - 256


@dataclass
class CCM15DeviceState:
    """Data retrieved from a CCM15 device."""

    devices: list[CCM15SlaveDevice]


class CCM15Coordinator(DataUpdateCoordinator[CCM15DeviceState]):
    """Class to coordinate multiple CCM15Climate devices."""

    def __init__(
        self, host: str, port: int, interval: int, hass: HomeAssistant
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=host,
            update_method=self._async_update_data,
            update_interval=datetime.timedelta(seconds=interval),
        )
        self._host = host
        self._port = port
        self._ac_devices: list[CCM15Climate] = []

    def get_devices(self):
        """Get all climate devices from the coordinator."""
        return self._ac_devices

    async def _async_update_data(self) -> CCM15DeviceState:
        """Fetch data from Rain Bird device."""
        try:
            return await self._fetch_data()
        except httpx.RequestError as err:
            raise UpdateFailed(f"Error communicating with Device: {err}") from err

    async def _fetch_data(self) -> CCM15DeviceState:
        """Get the current status of all AC devices."""
        url = BASE_URL.format(self._host, self._port, CONF_URL_STATUS)
        _LOGGER.debug("Querying url:'%s'", url)
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=DEFAULT_TIMEOUT)
        doc = xmltodict.parse(response.text)
        data = doc["response"]
        _LOGGER.debug("Found %s items in host %s", len(data.items()), self._host)
        ac_index = 0
        ac_data = CCM15DeviceState(devices=[])
        for ac_name, ac_binary in data.items():
            _LOGGER.debug("Found ac_name:'%s', data:'%s'", ac_name, ac_binary)
            if ac_binary == "-":
                break
            bytesarr = bytes.fromhex(ac_binary.strip(","))
            ac_slave = CCM15SlaveDevice(bytesarr)
            _LOGGER.debug("Index: %s, state:'%s'", ac_index, ac_slave)
            if len(self._ac_devices) == ac_index:
                _LOGGER.debug("Creating new ac device at index '%s'", ac_index)
                self._ac_devices.insert(
                    ac_index, CCM15Climate(self._host, ac_index, self)
                )
            ac_data.devices.insert(ac_index, ac_slave)
            ac_index += 1
        _LOGGER.debug("Found data '%s'", ac_data.devices)
        return ac_data

    async def async_test_connection(self):
        """Test the connection to the CCM15 device."""
        url = f"http://{self._host}:{self._port}/{CONF_URL_STATUS}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        return True
                    _LOGGER.debug(
                        "Test connection: Cannot connect : %s", response.status
                    )
                    return False
        except (aiohttp.ClientError, asyncio.TimeoutError):
            _LOGGER.debug("Test connection: Timeout")
            return False

    async def async_set_state(self, ac_index: int, state: str, value: int) -> None:
        """Set new target states."""
        _LOGGER.debug("Calling async_set_states for ac index '%s'", ac_index)
        ac_id: int = 2**ac_index
        url = BASE_URL.format(
            self._host,
            self._port,
            CONF_URL_CTRL
            + "?ac0="
            + str(ac_id)
            + "&ac1=0"
            + "&"
            + state
            + "="
            + str(value),
        )
        _LOGGER.debug("Url:'%s'", url)

        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=DEFAULT_TIMEOUT)
            if response.status_code in (httpx.codes.OK, httpx.codes.FOUND):
                _LOGGER.debug("API request ok %d", response.status_code)
                await self.async_request_refresh()
            else:
                _LOGGER.exception(
                    "Error doing API request: url: %s, code: %s",
                    url,
                    response.status_code,
                )

    def get_ac_data(self, ac_index: int) -> CCM15SlaveDevice:
        """Get ac data from the ac_index."""
        data = self.data.devices[ac_index]
        return data

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

    async def async_set_swing_mode(self, ac_index, swing_mode: int) -> None:
        """Set the fan mode."""
        _LOGGER.debug("Set Swing[%s]='%s'", ac_index, swing_mode)
        await self.async_set_state(ac_index, "swing", swing_mode)
