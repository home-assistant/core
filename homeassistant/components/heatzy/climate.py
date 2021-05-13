"""Climate sensors for Heatzy."""
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
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, PILOTEV1, PILOTEV2

MODE_LIST = [HVAC_MODE_HEAT, HVAC_MODE_OFF]
PRESET_LIST = [PRESET_NONE, PRESET_COMFORT, PRESET_ECO, PRESET_AWAY]

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=5)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Configure Heatzy API using Home Assistant configuration and fetch all Heatzy devices."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    devices = []
    for device in coordinator.data.values():
        product_key = device.get("product_key")
        if product_key in PILOTEV1:
            devices.append(HeatzyPiloteV1Thermostat(coordinator, device["did"]))
        elif product_key in PILOTEV2:
            devices.append(HeatzyPiloteV2Thermostat(coordinator, device["did"]))
    async_add_entities(devices)


class HeatzyThermostat(CoordinatorEntity, ClimateEntity):
    """Heatzy."""

    def __init__(self, coordinator, unique_id):
        """Init."""
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._unique_id = unique_id

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
        return self._unique_id

    @property
    def name(self):
        """Return a name."""
        return self._coordinator.data[self.unique_id]["dev_alias"]

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "name": self.name,
            "identifiers": {(DOMAIN, self.unique_id)},
            "manufacturer": DOMAIN,
            "model": self._coordinator.data[self.unique_id].get("product_name"),
            "sw_version": self._coordinator.data[self.unique_id].get(
                "wifi_soft_version"
            ),
        }

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes."""
        return MODE_LIST

    @property
    def hvac_mode(self):
        """Return hvac operation ie. heat, cool mode."""
        if self.preset_mode == PRESET_NONE:
            return HVAC_MODE_OFF
        return HVAC_MODE_HEAT

    @property
    def preset_modes(self):
        """Return a list of available preset modes."""
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
        """Return the current preset mode, e.g., home, away, temp."""
        return self.HEATZY_TO_HA_STATE.get(
            self._coordinator.data[self.unique_id].get("attr", {}).get("mode")
        )

    async def async_set_preset_mode(self, preset_mode):
        """Set new preset mode."""
        try:
            await self.hass.async_add_executor_job(
                self._coordinator.heatzy_client.control_device,
                self.unique_id,
                {"raw": self.HA_TO_HEATZY_STATE.get(preset_mode)},
            )
        except HeatzyException as error:
            _LOGGER.error("Error to set preset mode : %s", error)
        # await self.async_update_heater(True)
        await self.coordinator.async_request_refresh()


class HeatzyPiloteV2Thermostat(HeatzyThermostat):
    """Heaty Pilote v2."""

    # spell-checker:disable
    HEATZY_TO_HA_STATE = {
        "cft": PRESET_COMFORT,
        "eco": PRESET_ECO,
        "fro": PRESET_AWAY,
        "stop": PRESET_NONE,
    }

    HA_TO_HEATZY_STATE = {
        PRESET_COMFORT: "cft",
        PRESET_ECO: "eco",
        PRESET_AWAY: "fro",
        PRESET_NONE: "stop",
    }
    # spell-checker:enable

    @property
    def preset_mode(self):
        """Return the current preset mode, e.g., home, away, temp."""
        return self.HEATZY_TO_HA_STATE.get(
            self._coordinator.data[self.unique_id].get("attr", {}).get("mode")
        )

    async def async_set_preset_mode(self, preset_mode):
        """Set new preset mode."""
        try:
            await self.hass.async_add_executor_job(
                self._coordinator.heatzy_client.control_device,
                self.unique_id,
                {"attrs": {"mode": self.HA_TO_HEATZY_STATE.get(preset_mode)}},
            )
        except HeatzyException as error:
            _LOGGER.error("Error to set preset mode : %s", error)

        await self.coordinator.async_request_refresh()
