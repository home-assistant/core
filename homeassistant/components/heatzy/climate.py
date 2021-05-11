"""Climate sensors for Heatzy."""
import asyncio
from datetime import timedelta
import logging

from heatzypy.exception import HeatzyException

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    PRESET_AWAY,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    SUPPORT_PRESET_MODE,
)
from homeassistant.const import TEMP_CELSIUS
from homeassistant.util import Throttle

from .const import DOMAIN, HEATZY_API, HEATZY_DEVICES, PILOTEV1, PILOTEV2

MODE_LIST = [HVAC_MODE_HEAT, HVAC_MODE_OFF]
PRESET_LIST = [PRESET_NONE, PRESET_COMFORT, PRESET_ECO, PRESET_AWAY]

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=5)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Configure Heatzy API using Home Assistant configuration and fetch all Heatzy devices."""
    # heatzy_devices = hass.data[DOMAIN][HEATZY_DEVICES]
    # api = hass.data[DOMAIN][HEATZY_API]
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    devices = []
    for device in coordinator.data:
        product_key = device.get("product_key")
        if product_key in PILOTEV1:
            devices.append(HeatzyPiloteV1Thermostat(coordinator, device))
        elif product_key in PILOTEV2:
            devices.append(HeatzyPiloteV2Thermostat(coordinator, device))
    async_add_entities(devices, True)


class HeatzyThermostat(ClimateEntity):
    """Heatzy."""

    def __init__(self, coordinator, device):
        """Init."""
        self._coordinator = coordinator
        self._heater = device
        self._heater_data = {}
        self._available = True

    @property
    def temperature_unit(self):
        """Return the unit of measurement used by the platform."""
        return TEMP_CELSIUS

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_PRESET_MODE

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._heater.get("did")

    @property
    def name(self):
        """Return a name."""
        return self._heater.get("dev_alias")

    @property
    def available(self):
        """Return True if entity is available."""
        return self._available

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "name": self.name,
            "identifiers": {(DOMAIN, self.unique_id)},
            "manufacturer": DOMAIN,
            "model": self._heater.get("product_name"),
            "sw_version": self._heater.get("wifi_soft_version"),
        }

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes.

        Need to be a subset of HVAC_MODES.
        """
        return MODE_LIST

    @property
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode.

        Need to be one of HVAC_MODE_*.
        """
        if self.preset_mode == PRESET_NONE:
            return HVAC_MODE_OFF
        return HVAC_MODE_HEAT

    @property
    def preset_modes(self):
        """Return a list of available preset modes.

        Requires SUPPORT_PRESET_MODE.
        """
        return PRESET_LIST

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new hvac mode."""
        if hvac_mode == HVAC_MODE_OFF:
            await self.async_turn_off()
        elif hvac_mode == HVAC_MODE_HEAT:
            await self.async_turn_on()

    async def async_turn_on(self):
        """Turn device on."""
        await self.async_set_preset_mode(PRESET_COMFORT)

    async def async_turn_off(self):
        """Turn device off."""
        await self.async_set_preset_mode(PRESET_NONE)

    # async def async_update_heater(self, force_update=False):
    #     """Get the latest state from the thermostat."""
    #     if force_update is True:
    #         # Updated temperature to HA state to avoid flapping (API confirmation is slow)
    #         await asyncio.sleep(1)
    #     try:
    #         data_status = await self.hass.async_add_executor_job(
    #             self._coordinator.get_device, self.unique_id
    #         )
    #         if data_status:
    #             self._heater_data = data_status
    #             self._available = True
    #     except HeatzyException:
    #         _LOGGER.error("Device data no retrieve %s", self.name)
    #         self._available = False

    # @Throttle(SCAN_INTERVAL)
    # async def async_update(self):
    #     """Update device."""
    #     await self.async_update_heater()


class HeatzyPiloteV1Thermostat(HeatzyThermostat):
    """Heaty Pilote v1."""

    HEATZY_TO_HA_STATE = {
        "\u8212\u9002": PRESET_COMFORT,
        "\u7ecf\u6d4e": PRESET_ECO,
        "\u89e3\u51bb": PRESET_AWAY,
        "\u505c\u6b62": PRESET_NONE,
    }
    HA_TO_HEATZY_STATE = {
        PRESET_COMFORT: [1, 1, 0],
        PRESET_ECO: [1, 1, 1],
        PRESET_AWAY: [1, 1, 2],
        PRESET_NONE: [1, 1, 3],
    }

    @property
    def preset_mode(self):
        """Return the current preset mode, e.g., home, away, temp.

        Requires SUPPORT_PRESET_MODE.
        """
        return self.HEATZY_TO_HA_STATE.get(
            self._heater_data.get("attr", {}).get("mode")
        )

    async def async_set_preset_mode(self, preset_mode):
        """Set new preset mode."""
        try:
            await self.hass.async_add_executor_job(
                self._coordinator.control_device,
                self.unique_id,
                {"raw": self.HA_TO_HEATZY_STATE.get(preset_mode)},
            )
        except HeatzyException as error:
            _LOGGER.error("Error to set preset mode : %s", error)
        # await self.async_update_heater(True)
        await self.coordinator.async_request_refresh()


class HeatzyPiloteV2Thermostat(HeatzyThermostat):
    """Heaty Pilote v2."""

    HEATZY_TO_HA_STATE = {
        "cft": PRESET_COMFORT,
        "eco": PRESET_ECO,
        "fro": PRESET_AWAY,  # codespell: ignore-words fro
        "stop": PRESET_NONE,
    }

    HA_TO_HEATZY_STATE = {
        PRESET_COMFORT: "cft",
        PRESET_ECO: "eco",
        PRESET_AWAY: "fro",  # codespell: ignore-words fro
        PRESET_NONE: "stop",
    }

    @property
    def preset_mode(self):
        """Return the current preset mode, e.g., home, away, temp.

        Requires SUPPORT_PRESET_MODE.
        """
        return self.HEATZY_TO_HA_STATE.get(
            self._heater_data.get("attr", {}).get("mode")
        )

    async def async_set_preset_mode(self, preset_mode):
        """Set new preset mode."""
        try:
            await self.hass.async_add_executor_job(
                self._coordinator.control_device,
                self.unique_id,
                {"attrs": {"mode": self.HA_TO_HEATZY_STATE.get(preset_mode)}},
            )
        except HeatzyException as error:
            _LOGGER.error("Error to set preset mode : %s", error)
        # await self.async_update_heater(True)
        await self.coordinator.async_request_refresh()
