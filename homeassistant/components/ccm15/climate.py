"""Climate device for CCM15 coordinator."""
import asyncio
import logging

import aiohttp
import httpx
import xmltodict

from homeassistant.components.climate import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
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

from .const import BASE_URL, CONF_URL_STATUS, DEFAULT_INTERVAL, DEFAULT_TIMEOUT, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONST_MODE_MAP = {
    "off": 0,
    "cool": 2,
    "dry": 3,
    "fan_only": 4,
    "heat": 6,
}

CONST_FAN_MAP = {
    "auto": 0,
    "high": 3,
    "med": 2,
    "low": 1,
}


class CCM15Coordinator:
    """Class to coordinate multiple CCM15Climate devices."""

    def __init__(self, host: str, port: int, interval: int = DEFAULT_INTERVAL) -> None:
        """Initialize the coordinator."""
        self._host = host
        self._port = port
        self._interval = interval
        self._ac_devices: dict[int, CCM15Climate] = {}
        self._ac_data: dict[int, dict[str, int]] = {}
        self._running = False

    async def init_async(self):
        """Start polling."""
        if self._running:
            return
        self._running = True
        while self._running:
            await self.poll_status_async()
            await asyncio.sleep(self._interval)

    async def deinit_async(self):
        """Stop polling."""
        if self._running:
            self._running = False
            await self._poll_task

    def add_device(self, device):
        """Add a new device to the coordinator."""
        self._ac_devices[device.ac_id] = device

    def remove_device(self, ac_id):
        """Remove a device from the coordinator."""
        if ac_id in self._ac_devices:
            del self._ac_devices[ac_id]

    def get_devices(self):
        """Get all climate devices from the coordinator."""
        return self._ac_devices

    async def poll_status_async(self):
        """Get the current status of all AC devices."""
        try:
            url = BASE_URL.format(self._host, self._port, CONF_URL_STATUS)
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=DEFAULT_TIMEOUT)
        except httpx.RequestError as err:
            _LOGGER.exception("Exception retrieving API data %s", err)
        else:
            doc = xmltodict.parse(response.text)
            data = doc["response"]
            for ac_name, ac_binary in data.items():
                if len(ac_binary) > 1:
                    ac_state = self.get_status_from(ac_binary)
                if ac_state:
                    if ac_name in self._ac_devices:
                        self._ac_devices[ac_name].update_with_acdata(ac_state)
                    else:
                        _LOGGER.debug("AC device %s not registered", ac_name)

    def get_status_from(self, ac_binary: str) -> dict[str, int]:
        """Parse the binary data and return a dictionary with AC status."""
        # Parse data from the binary stream
        return {}

    def update_climates_from_status(self, ac_status):
        """Update climate devices from the latest status."""
        for ac_name in ac_status:
            if not ac_status[ac_name]:
                # Ignore empty entries
                continue
            if ac_name not in self._ac_devices:
                # Create new climate entity if it doesn't exist
                int(ac_status[ac_name]["id"])
                self._ac_devices[ac_name] = CCM15Climate(
                    ac_name, self._host, self._port, self
                )
                _LOGGER.debug("New climate created: %s", ac_name)
            else:
                # Update existing climate entity
                self._ac_devices[ac_name].updateWithAcdata(ac_status[ac_name])
                _LOGGER.debug("Climate updated: %s", ac_name)

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
        self, ac_name: str, host: str, port: int, coordinator: CCM15Coordinator
    ) -> None:
        """Create a climate device managed from a coordinator."""
        self._ac_name = ac_name
        self._host = host
        self._port = port
        self._coordinator = coordinator
        self._data: dict[str, int] = {}
        self._is_on = False
        self._current_temp = None
        self._target_temp = None
        self._operation_mode = None
        self._fan_mode = None
        self._swing_mode = None
        self._available = False
        self.update()

    @property
    def unique_id(self):
        """Return unique id."""
        return f"{self._host}:{self._port}:{self._ac_name}"

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
            | ClimateEntityFeature.PRESET_MODE
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
        self._coordinator.get_acdata(self._ac_name)
        self.schedule_update_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up all climate."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities = []
    for ac_device in coordinator.get_devices():
        entities.append(ac_device.CCM15Coordinator)
    async_add_entities(entities, True)
