"""Climate device for CCM15 coordinator."""
import asyncio
from dataclasses import dataclass
import datetime
import logging
from typing import Any

import aiohttp
import httpx
import xmltodict

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_OFF,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_VERTICAL,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    BASE_URL,
    CONF_URL_CTRL,
    CONF_URL_STATUS,
    DEFAULT_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

CONST_STATE_CMD_MAP = {
    HVACMode.COOL: 0,
    HVACMode.HEAT: 1,
    HVACMode.DRY: 2,
    HVACMode.FAN_ONLY: 3,
    HVACMode.OFF: 4,
    HVACMode.AUTO: 5,
}
CONST_CMD_STATE_MAP = {v: k for k, v in CONST_STATE_CMD_MAP.items()}
CONST_FAN_CMD_MAP = {FAN_AUTO: 0, FAN_LOW: 2, FAN_MEDIUM: 3, FAN_HIGH: 4, FAN_OFF: 5}
CONST_CMD_FAN_MAP = {v: k for k, v in CONST_FAN_CMD_MAP.items()}


@dataclass
class CCM15SlaveDevice:
    """Data retrieved from a CCM15 slave device."""

    def __init__(self, bytesarr: bytes) -> None:
        """Initialize the slave device."""
        self.wind_mode = 0
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

    async def async_set_states(
        self, ac_index: int, state_cmd: int, fan_cmd: int, temp: int
    ):
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
            + "&mode="
            + str(state_cmd)
            + "&fan="
            + str(fan_cmd)
            + "&temp="
            + str(temp),
        )
        _LOGGER.debug("Url:'%s'", url)

        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=DEFAULT_TIMEOUT)
            if response.status_code != httpx.codes.OK:
                _LOGGER.exception(
                    "Error doing API request: url: %s, code: %s",
                    url,
                    response.status_code,
                )
            else:
                _LOGGER.debug("API request ok %d", response.status_code)
                await self.async_request_refresh()

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


class CCM15Climate(CoordinatorEntity[CCM15Coordinator], ClimateEntity):
    """Climate device for CCM15 coordinator."""

    def __init__(
        self, ac_host: str, ac_index: int, coordinator: CCM15Coordinator
    ) -> None:
        """Create a climate device managed from a coordinator."""
        super().__init__(coordinator)
        self._ac_host: str = ac_host
        self._ac_index: int = ac_index
        self._ac_name: str = f"ac{self._ac_index}"

    @property
    def unique_id(self) -> str:
        """Return unique id."""
        return f"{self._ac_host}.{self._ac_name}"

    @property
    def name(self) -> str:
        """Return name."""
        return f"{self._ac_name} thermostat"

    @property
    def should_poll(self) -> bool:
        """Return if should poll."""
        return True

    @property
    def temperature_unit(self) -> UnitOfTemperature:
        """Return temperature unit."""
        data: CCM15SlaveDevice = self.coordinator.get_ac_data(self._ac_index)
        _LOGGER.debug("unit[%s]=%s", self._ac_index, str(data.unit))
        return data.unit

    @property
    def current_temperature(self) -> int:
        """Return current temperature."""
        data: CCM15SlaveDevice = self.coordinator.get_ac_data(self._ac_index)
        _LOGGER.debug("temp[%s]=%s", self._ac_index, data.temperature)
        return data.temperature

    @property
    def target_temperature(self) -> int:
        """Return target temperature."""
        data: CCM15SlaveDevice = self.coordinator.get_ac_data(self._ac_index)
        _LOGGER.debug("set_temp[%s]=%s", self._ac_index, data.temperature_setpoint)
        return data.temperature_setpoint

    @property
    def target_temperature_step(self) -> int:
        """Return target temperature step."""
        return 1

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac mode."""
        data: CCM15SlaveDevice = self.coordinator.get_ac_data(self._ac_index)
        mode = data.ac_mode
        _LOGGER.debug("hvac_mode[%s]=%s", self._ac_index, mode)
        return CONST_CMD_STATE_MAP[mode]

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return hvac modes."""
        return [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL, HVACMode.DRY, HVACMode.AUTO]

    @property
    def fan_mode(self) -> str:
        """Return fan mode."""
        data: CCM15SlaveDevice = self.coordinator.get_ac_data(self._ac_index)
        mode = data.fan_mode
        _LOGGER.debug("fan_mode[%s]=%s", self._ac_index, mode)
        return CONST_CMD_FAN_MAP[mode]

    @property
    def fan_modes(self) -> list[str]:
        """Return fan modes."""
        return [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH]

    @property
    def swing_mode(self) -> str:
        """Return swing mode."""
        return SWING_OFF

    @property
    def swing_modes(self) -> list[str]:
        """Return swing modes."""
        return [SWING_OFF, SWING_VERTICAL, SWING_HORIZONTAL, SWING_BOTH]

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return supported features."""
        return (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.SWING_MODE
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        await self.coordinator.async_set_temperature(self._ac_index, temperature)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the hvac mode."""
        await self.coordinator.async_set_hvac_mode(self._ac_index, hvac_mode)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode."""
        await self.coordinator.async_set_fan_mode(self._ac_index, fan_mode)

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set the swing mode."""

    async def async_turn_off(self) -> None:
        """Turn off."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_turn_on(self) -> None:
        """Turn on."""
        await self.async_set_hvac_mode(HVACMode.AUTO)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up all climate."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities = []
    for ac_device in coordinator.get_devices():
        entities.append(ac_device)
    async_add_entities(entities, True)
