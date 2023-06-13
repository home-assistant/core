"""Climate device for CCM15 coordinator."""
import asyncio
from dataclasses import dataclass
import datetime
import logging

import aiohttp
import async_timeout
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
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import BASE_URL, CONF_URL_STATUS, DEFAULT_INTERVAL, DEFAULT_TIMEOUT, DOMAIN

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

    devices: list[dict[int, str]]


class CCM15Coordinator(DataUpdateCoordinator[CCM15DeviceState]):
    """Class to coordinate multiple CCM15Climate devices."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        interval: int = DEFAULT_INTERVAL,
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
        self._ac_devices: list[CCM15Climate]

    def get_devices(self):
        """Get all climate devices from the coordinator."""
        return self._ac_devices

    async def _async_update_data(self) -> CCM15DeviceState:
        """Fetch data from Rain Bird device."""
        try:
            async with async_timeout.timeout(DEFAULT_TIMEOUT):
                return await self._fetch_data()
        except httpx.RequestError as err:
            _LOGGER.exception("Exception retrieving API data %s", err)
            raise UpdateFailed(f"Error communicating with Device: {err}") from err

    async def _fetch_data(self) -> CCM15DeviceState:
        """Get the current status of all AC devices."""
        try:
            url = BASE_URL.format(self._host, self._port, CONF_URL_STATUS)
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=DEFAULT_TIMEOUT)
        except httpx.RequestError as err:
            _LOGGER.exception("Exception retrieving API data %s", err)
            raise UpdateFailed(f"Error communicating with Device: {err}") from err

        doc = xmltodict.parse(response.text)
        data = doc["response"]
        _LOGGER.debug("Found %s items in host %s", len(data.items()), self._host)
        ac_index = 0
        ac_data: list[dict[str, int]] = []
        for ac_name, ac_binary in data.items():
            _LOGGER.debug("Found ac_name:'%s', data:'%s'", ac_name, ac_binary)
            ac_state = self.get_status_from(ac_binary)
            if ac_state:
                _LOGGER.debug("Parsed data ac_state:'%s'", ac_state)
                if self._ac_devices[ac_index] is None:
                    _LOGGER.debug("Creating new ac device '%s'", ac_name)
                    self._ac_devices[ac_index] = CCM15Climate(
                        self._host, ac_index, self
                    )
                ac_data.insert(ac_index, ac_state)
                ac_index += 1
            else:
                break
        data = CCM15DeviceState
        data.devices = ac_state
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


class CCM15Climate(ClimateEntity):
    """Climate device for CCM15 coordinator."""

    def __init__(
        self, ac_host: str, ac_index: int, coordinator: CCM15Coordinator
    ) -> None:
        """Create a climate device managed from a coordinator."""
        self._ac_host = ac_host
        self._ac_index = ac_index
        self._ac_name = f"ac{self._ac_index}"
        self._coordinator = coordinator
        self._is_on = False
        self._current_temp = 0
        self._target_temp = 0
        self._operation_mode = HVACMode.OFF
        self._fan_mode = FAN_OFF
        self._swing_mode = SWING_OFF
        self._available = False

    def update_from_ac_data(self, acdata: dict[str, int]):
        """Update state from the ac_data."""

        self._available = True
        self._current_temp = acdata["temp"]
        self._target_temp = acdata["settemp"]
        self._operation_mode = CONST_CMD_STATE_MAP[acdata["ac_mode"]]
        self._fan_mode = CONST_CMD_FAN_MAP[acdata["fan"]]

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
        return self._current_temp

    @property
    def target_temperature(self):
        """Return target temperature."""
        return self._target_temp

    @property
    def target_temperature_step(self):
        """Return target temperature step."""
        return 1

    @property
    def hvac_mode(self):
        """Return hvac mode."""
        return self._operation_mode

    @property
    def hvac_modes(self):
        """Return hvac modes."""
        return [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO]

    @property
    def fan_mode(self):
        """Return fan mode."""
        return self._fan_mode

    @property
    def fan_modes(self):
        """Return fan modes."""
        return [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH]

    @property
    def swing_mode(self):
        """Return swing mode."""
        return self._swing_mode

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

    def set_temperature(self, **kwargs):
        """Set the target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        self._target_temp = temperature
        self._coordinator.set_temperature(self._ac_name, temperature)
        self.schedule_update_ha_state()

    def set_hvac_mode(self, hvac_mode):
        """Set the hvac mode."""
        self._operation_mode = hvac_mode
        self._coordinator.set_operation_mode(self._ac_name, hvac_mode)
        self.schedule_update_ha_state()

    def set_fan_mode(self, fan_mode):
        """Set the fan mode."""
        self._fan_mode = fan_mode
        self._coordinator.set_fan_mode(self._ac_name, fan_mode)
        self.schedule_update_ha_state()

    def set_swing_mode(self, swing_mode):
        """Set the swing mode."""
        self._swing_mode = swing_mode
        self._coordinator.set_swing_mode(self._ac_name, swing_mode)
        self.schedule_update_ha_state()

    def turn_off(self):
        """Turn off."""
        self._is_on = False
        self._coordinator.turn_off(self._ac_name)
        self.schedule_update_ha_state()

    def turn_on(self):
        """Turn on."""
        self._is_on = True
        self._coordinator.turn_on(self._ac_name)
        self.schedule_update_ha_state()

    def update(self):
        """Update the data from the thermostat."""


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up all climate."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    await coordinator.poll_status_async()
    entities = []
    for ac_device in coordinator.get_devices():
        entities.append(ac_device)
    async_add_entities(entities, True)
