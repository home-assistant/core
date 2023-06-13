"""Climate device for CCM15 coordinator."""
import asyncio
from dataclasses import dataclass
import datetime
import logging

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
class CCM15DeviceState:
    """Data retrieved from a CCM15 device."""

    devices: list[dict[str, int]]


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
        ac_data: list[dict[str, int]] = []
        for ac_name, ac_binary in data.items():
            _LOGGER.debug("Found ac_name:'%s', data:'%s'", ac_name, ac_binary)
            ac_state = self.get_status_from(ac_binary)
            if ac_state:
                _LOGGER.debug("Index: %s, state:'%s'", ac_index, ac_state)
                if len(self._ac_devices) == ac_index:
                    _LOGGER.debug("Creating new ac device at index '%s'", ac_index)
                    self._ac_devices.insert(
                        ac_index, CCM15Climate(self._host, ac_index, self)
                    )
                ac_data.insert(ac_index, ac_state)
                ac_index += 1
            else:
                break
        data = CCM15DeviceState
        data.devices = ac_data
        _LOGGER.debug("Found data '%s'", data.devices)
        return data

    def get_status_from(self, ac_binary: str) -> dict[str, int]:
        """Parse the binary data and return a dictionary with AC status."""
        # Parse data from the binary stream
        if ac_binary == "-":
            return {}

        locked_wind = 0
        locked_mode = 0
        mode_locked = 0
        fan_locked = 0
        ctl = 0
        htl = 0
        rml = 0
        mode = 0
        fan = 0
        temp = 0
        err = 0
        settemp = 0

        bytesarr = bytes.fromhex(ac_binary.strip(","))

        buf = bytesarr[0]
        is_farenheith = (buf >> 0) & 1
        ctl = (buf >> 3) & 0x1F

        buf = bytesarr[1]
        htl = (buf >> 0) & 0x1F
        locked_wind = (buf >> 5) & 7

        buf = bytesarr[2]
        locked_mode = (buf >> 0) & 3
        err = (buf >> 2) & 0x3F

        if locked_mode == 1:
            locked_mode = 0
        elif locked_mode == 2:
            locked_mode = 1
        else:
            locked_mode = -1

        buf = bytesarr[3]
        mode = (buf >> 2) & 7
        fan = (buf >> 5) & 7
        buf = (buf >> 1) & 1
        if buf != 0:
            mode_locked = 1

        buf = bytesarr[4]
        settemp = (buf >> 3) & 0x1F
        if is_farenheith:
            settemp += 62
            ctl += 62
            htl += 62

        buf = bytesarr[5]
        if ((buf >> 3) & 1) == 0:
            ctl = 0
        if ((buf >> 4) & 1) == 0:
            htl = 0
        fan_locked = 0 if ((buf >> 5) & 1) == 0 else 1
        if ((buf >> 6) & 1) != 0:
            rml = 1

        buf = bytesarr[6]
        temp = buf if buf < 128 else buf - 256

        ac_data = {}
        ac_data["ac_mode"] = mode
        ac_data["fan"] = fan
        ac_data["temp"] = temp
        ac_data["settemp"] = settemp
        ac_data["err"] = err
        ac_data["locked"] = 0
        if mode_locked == 1 or fan_locked == 1 or ctl > 0 or htl > 0 or rml == 1:
            ac_data["locked"] = 1
        ac_data["l_rm"] = rml

        ac_data["l_mode"] = 10 if mode_locked == 0 else locked_mode
        ac_data["l_wind"] = 10 if fan_locked == 0 else locked_wind

        ac_data["l_cool_temp"] = ctl
        ac_data["l_heat_temp"] = htl

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

    async def async_set_states(
        self, ac_id: int, state_cmd: int, fan_cmd: int, temp: int
    ):
        """Set new target states."""
        _LOGGER.debug("Calling async_set_states for ac index '%s'", ac_id)

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
                _LOGGER.exception("Error doing API request")
            else:
                _LOGGER.debug("API request ok %d", response.status_code)
                await self.async_request_refresh()

    def get_ac_data(self, ac_index: int) -> dict[str, int]:
        """Get ac data from the ac_index."""
        _LOGGER.debug("Getting data '%s' at index '%s'", self.data.devices, ac_index)
        data = self.data.devices[ac_index]
        _LOGGER.debug("Data '%s'", data)
        return data

    async def async_set_hvac_mode(self, ac_index, hvac_mode):
        """Set the hvac mode."""
        data = self.get_ac_data(ac_index)
        await self.async_set_states(
            ac_index,
            CONST_STATE_CMD_MAP[hvac_mode],
            data["fan"],
            data["temp"],
        )

    async def async_set_fan_mode(self, ac_index, fan_mode):
        """Set the fan mode."""
        data = self.get_ac_data(ac_index)
        await self.async_set_states(
            ac_index,
            data["mode"],
            CONST_FAN_CMD_MAP[fan_mode],
            data["temp"],
        )


class CCM15Climate(CoordinatorEntity[CCM15Coordinator], ClimateEntity):
    """Climate device for CCM15 coordinator."""

    def __init__(
        self, ac_host: str, ac_index: int, coordinator: CCM15Coordinator
    ) -> None:
        """Create a climate device managed from a coordinator."""
        super().__init__(coordinator)
        self._ac_host = ac_host
        self._ac_index = ac_index
        self._ac_name = f"ac{self._ac_index}"

    @property
    def unique_id(self):
        """Return unique id."""
        return f"{self._ac_host}.{self._ac_name}"

    @property
    def name(self):
        """Return name."""
        return f"{self._ac_name} thermostat"

    @property
    def should_poll(self) -> bool:
        """Return if should poll."""
        return True

    @property
    def temperature_unit(self):
        """Return temperature unit."""
        return UnitOfTemperature.CELSIUS

    @property
    def current_temperature(self):
        """Return current temperature."""
        return self.coordinator.data.devices[self._ac_index]["temp"]

    @property
    def target_temperature(self):
        """Return target temperature."""
        return self.coordinator.data.devices[self._ac_index]["settemp"]

    @property
    def target_temperature_step(self):
        """Return target temperature step."""
        return 1

    @property
    def hvac_mode(self):
        """Return hvac mode."""
        data = self.coordinator.get_ac_data(self._ac_index)
        mode = data["ac_mode"]
        _LOGGER.debug("Hvac mode '%s'", mode)
        return CONST_CMD_STATE_MAP[mode]

    @property
    def hvac_modes(self):
        """Return hvac modes."""
        return [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO]

    @property
    def fan_mode(self):
        """Return fan mode."""
        return CONST_CMD_FAN_MAP[self.coordinator.data.devices[self._ac_index]["fan"]]

    @property
    def fan_modes(self):
        """Return fan modes."""
        return [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH]

    @property
    def swing_mode(self):
        """Return swing mode."""
        return SWING_OFF

    @property
    def swing_modes(self) -> list[str]:
        """Return swing modes."""
        return [SWING_OFF, SWING_VERTICAL, SWING_HORIZONTAL, SWING_BOTH]

    @property
    def supported_features(self):
        """Return supported features."""
        return (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.FAN_MODE
            | ClimateEntityFeature.SWING_MODE
        )

    async def async_set_temperature(self, **kwargs):
        """Set the target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        await self.coordinator.async_set_temperature(self._ac_index, temperature)

    async def async_set_hvac_mode(self, hvac_mode):
        """Set the hvac mode."""
        await self.coordinator.async_set_hvac_mode(self._ac_index, hvac_mode)

    async def async_set_fan_mode(self, fan_mode):
        """Set the fan mode."""
        await self.coordinator.async_set_fan_mode(self._ac_index, fan_mode)

    async def async_set_swing_mode(self, swing_mode):
        """Set the swing mode."""
        await self.coordinator.async_set_swing_mode(self._ac_index, swing_mode)

    async def async_turn_off(self):
        """Turn off."""
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_turn_on(self):
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
