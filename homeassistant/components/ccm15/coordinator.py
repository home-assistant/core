"""Climate device for CCM15 coordinator."""
import asyncio
import datetime
import logging
from typing import Any, Optional

import aiohttp
import httpx
import xmltodict

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    SWING_OFF,
    SWING_ON,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    BASE_URL,
    CONF_URL_CTRL,
    CONF_URL_STATUS,
    CONST_CMD_FAN_MAP,
    CONST_CMD_STATE_MAP,
    CONST_FAN_CMD_MAP,
    CONST_STATE_CMD_MAP,
    DEFAULT_TIMEOUT,
    DOMAIN,
)
from .data_model import CCM15DeviceState, CCM15SlaveDevice

_LOGGER = logging.getLogger(__name__)


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
        self._ac_devices: dict[int, CCM15Climate] = {}

    def get_devices(self):
        """Get all climate devices from the coordinator."""
        return self._ac_devices.values()

    async def _async_update_data(self) -> CCM15DeviceState:
        """Fetch data from Rain Bird device."""
        try:
            return await self._fetch_data()
        except httpx.RequestError as err:  # pragma: no cover
            raise UpdateFailed(f"Error communicating with Device: {err}") from err

    async def _fetch_xml_data(self) -> str:  # pragma: no cover
        url = BASE_URL.format(self._host, self._port, CONF_URL_STATUS)
        _LOGGER.debug("Querying url:'%s'", url)
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=DEFAULT_TIMEOUT)
        return response.text

    async def _fetch_data(self) -> CCM15DeviceState:
        """Get the current status of all AC devices."""
        str_data = await self._fetch_xml_data()
        doc = xmltodict.parse(str_data)
        data = doc["response"]
        _LOGGER.debug("Found %s items in host %s", len(data.items()), self._host)
        ac_data = CCM15DeviceState(devices={})
        ac_index = 0
        for ac_name, ac_binary in data.items():
            _LOGGER.debug("Found ac_name:'%s', data:'%s'", ac_name, ac_binary)
            if ac_binary == "-":
                break
            bytesarr = bytes.fromhex(ac_binary.strip(","))
            ac_slave = CCM15SlaveDevice(bytesarr)
            _LOGGER.debug("Index: %s, state:'%s'", ac_index, ac_slave)
            ac_data.devices[ac_index] = ac_slave
            ac_index += 1
        _LOGGER.debug("Found data '%s'", ac_data.devices)
        if len(self._ac_devices) == 0:
            for ac_index in ac_data.devices:
                _LOGGER.debug("Creating new ac device at index '%s'", ac_index)
                self._ac_devices[ac_index] = CCM15Climate(self._host, ac_index, self)
        return ac_data

    async def async_test_connection(self):  # pragma: no cover
        """Test the connection to the CCM15 device."""
        url = f"http://{self._host}:{self._port}/{CONF_URL_STATUS}"
        try:
            async with aiohttp.ClientSession() as session, session.get(
                url, timeout=10
            ) as response:
                if response.status == 200:
                    return True
                _LOGGER.debug("Test connection: Cannot connect : %s", response.status)
                return False
        except (aiohttp.ClientError, asyncio.TimeoutError):
            _LOGGER.debug("Test connection: Timeout")
            return False

    async def async_send_state(self, url: str) -> bool:  # pragma: no cover
        """Send the url to set state to the ccm15 slave."""
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=DEFAULT_TIMEOUT)
            _LOGGER.debug("API response status code:%d", response.status_code)
            return response.status_code in (httpx.codes.OK, httpx.codes.FOUND)

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

        if await self.async_send_state(url):
            await self.async_request_refresh()

    def get_ac_data(self, ac_index: int) -> Optional[CCM15SlaveDevice]:
        """Get ac data from the ac_index."""
        if ac_index < 0 or ac_index >= len(self.data.devices):
            # Index is out of bounds or not an integer
            return None
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

    @property
    def unique_id(self) -> str:
        """Return unique id."""
        return f"{self._ac_host}.{self._ac_index}"

    @property
    def name(self) -> str:
        """Return name."""
        return f"Climate{self._ac_index}"

    @property
    def should_poll(self) -> bool:
        """Return if should poll."""
        return True

    @property
    def temperature_unit(self) -> UnitOfTemperature:
        """Return temperature unit."""
        return UnitOfTemperature.CELSIUS

    @property
    def current_temperature(self) -> Optional[int]:
        """Return current temperature."""
        data: Optional[CCM15SlaveDevice] = self.coordinator.get_ac_data(self._ac_index)
        if data is None:
            # Data is not available for the given AC index
            _LOGGER.warning("Data is not available for AC index %s", self._ac_index)
            return None

        _LOGGER.debug("temp[%s]=%s", self._ac_index, data.temperature)
        return data.temperature

    @property
    def target_temperature(self) -> Optional[int]:
        """Return target temperature."""
        data: Optional[CCM15SlaveDevice] = self.coordinator.get_ac_data(self._ac_index)
        if data is None:
            # Data is not available for the given AC index
            _LOGGER.warning("Data is not available for AC index %s", self._ac_index)
            return None

        _LOGGER.debug("set_temp[%s]=%s", self._ac_index, data.temperature_setpoint)
        return data.temperature_setpoint

    @property
    def target_temperature_step(self) -> int:
        """Return target temperature step."""
        return 1

    @property
    def hvac_mode(self) -> Optional[HVACMode]:
        """Return hvac mode."""
        data: Optional[CCM15SlaveDevice] = self.coordinator.get_ac_data(self._ac_index)
        if data is None:
            # Data is not available for the given AC index
            _LOGGER.warning("Data is not available for AC index %s", self._ac_index)
            return None

        mode = data.ac_mode
        _LOGGER.debug("hvac_mode[%s]=%s", self._ac_index, mode)
        return CONST_CMD_STATE_MAP[mode]

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return hvac modes."""
        return [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL, HVACMode.DRY, HVACMode.AUTO]

    @property
    def fan_mode(self) -> Optional[str]:
        """Return fan mode."""
        data: Optional[CCM15SlaveDevice] = self.coordinator.get_ac_data(self._ac_index)
        if data is None:
            # Data is not available for the given AC index
            _LOGGER.warning("Data is not available for AC index %s", self._ac_index)
            return None
        mode = data.fan_mode
        _LOGGER.debug("fan_mode[%s]=%s", self._ac_index, mode)
        return CONST_CMD_FAN_MAP[mode]

    @property
    def fan_modes(self) -> list[str]:
        """Return fan modes."""
        return [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH]

    @property
    def swing_mode(self) -> Optional[str]:
        """Return swing mode."""
        data: Optional[CCM15SlaveDevice] = self.coordinator.get_ac_data(self._ac_index)
        if data is None:
            # Data is not available for the given AC index
            _LOGGER.warning("Data is not available for AC index %s", self._ac_index)
            return None
        _LOGGER.debug("is_swing_on[%s]=%s", self._ac_index, data.is_swing_on)
        return SWING_ON if data.is_swing_on else SWING_OFF

    @property
    def swing_modes(self) -> list[str]:
        """Return swing modes."""
        return [SWING_OFF, SWING_ON]

    @property
    def supported_features(self) -> ClimateEntityFeature:
        """Return supported features."""
        return (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.SWING_MODE
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, f"{self._ac_host}.{self._ac_index}"),
            },
            name=self.name,
            manufacturer="Midea",
            model="CCM15",
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the optional state attributes."""
        data: Optional[CCM15SlaveDevice] = self.coordinator.get_ac_data(self._ac_index)
        if data is None:
            # Data is not available for the given AC index
            _LOGGER.warning("Data is not available for AC index %s", self._ac_index)
            return {}
        return {"error_code": data.error_code}

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

    async def async_turn_off(self) -> None:
        """Turn off."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_turn_on(self) -> None:
        """Turn on."""
        await self.async_set_hvac_mode(HVACMode.AUTO)
