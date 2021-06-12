"""Support for Alpha2 room control unit via Alpha2 base."""
import logging

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVAC_MODE_AUTO,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DOMAIN, SIGNAL_HEATAREA_DATA_UPDATED

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up platform."""
    return None


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add Alpha2Climate entities from a config_entry."""

    base_update_handler = hass.data[DOMAIN][config_entry.entry_id]["connection"]
    await base_update_handler.async_update()

    entities = []
    for heatarea in base_update_handler.base.heatareas:
        entities.append(Alpha2Climate(base_update_handler, heatarea))
    async_add_entities(entities)


# https://developers.home-assistant.io/docs/core/entity/climate/
class Alpha2Climate(ClimateEntity):
    """Alpha2 ClimateEntity."""

    target_temperature_step = 0.2

    def __init__(self, base_update_handler, data):
        """Initialize Alpha2 ClimateEntity."""
        self._base_update_handler = base_update_handler
        self._data = data

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_HEATAREA_DATA_UPDATED,
                self._handle_heatarea_data_updated,
            )
        )

    def _handle_heatarea_data_updated(self, data):
        """Handle updated heatarea data."""
        if data["NR"] == self._data["NR"]:
            self._data = data
            self.async_schedule_update_ha_state()

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE

    @property
    def should_poll(self):
        """Disable polling."""
        return False

    @property
    def name(self):
        """Return the name of the climate device."""
        return self._data["HEATAREA_NAME"]

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return float(self._data.get("T_TARGET_MIN", 0))

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return float(self._data.get("T_TARGET_MAX", 30))

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return float(self._data.get("T_ACTUAL", 0))

    @property
    def hvac_mode(self):
        """Return current operation mode."""
        return HVAC_MODE_AUTO

    @property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        return [HVAC_MODE_AUTO]

    def set_hvac_mode(self, hvac_mode: str):
        """Set new target hvac mode."""
        return

    @property
    def hvac_action(self):
        """Return the current running hvac operation if supported."""
        return None

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return float(self._data.get("T_TARGET", 0))

    async def async_set_temperature(self, **kwargs):
        """Set new target temperatures."""
        target_temperature = kwargs.get(ATTR_TEMPERATURE)
        if target_temperature is None:
            return False

        try:
            await self._base_update_handler.async_set_target_temperature(
                self._data["ID"], target_temperature
            )
            self._data["T_TARGET"] = target_temperature
            return True
        except Exception as update_err:  # pylint: disable=broad-except
            _LOGGER.error("Setting target temperature failed: %s", update_err)
            return False

    @property
    def preset_mode(self):
        """Return the current preset mode."""
        # HEATAREA_MODE: 0=Auto, 1=Tag, 2=Nacht
        if self._data["HEATAREA_MODE"] == 1:
            return PRESET_COMFORT
        if self._data["HEATAREA_MODE"] == 2:
            return PRESET_ECO
        return PRESET_NONE

    @property
    def preset_modes(self):
        """Return available preset modes."""
        return [PRESET_NONE, PRESET_COMFORT, PRESET_ECO]

    async def async_set_preset_mode(self, preset_mode):
        """Set new operation mode."""
        # HEATAREA_MODE: 0=Auto, 1=Tag, 2=Nacht
        heatarea_mode = 0
        if preset_mode == PRESET_COMFORT:
            heatarea_mode = 1
        elif preset_mode == PRESET_ECO:
            heatarea_mode = 2

        try:
            await self._base_update_handler.async_set_heatarea_mode(
                self._data["ID"], heatarea_mode
            )
            self._data["HEATAREA_MODE"] = heatarea_mode
            if heatarea_mode == 1:
                self._data["T_TARGET"] = self._data["T_HEAT_DAY"]
            elif heatarea_mode == 2:
                self._data["T_TARGET"] = self._data["T_HEAT_NIGHT"]
            return True
        except Exception as update_err:  # pylint: disable=broad-except
            _LOGGER.error("Setting target temperature failed: %s", update_err)
            return False

    @property
    def device_state_attributes(self):
        """Return the optional state attributes."""
        data = super().device_state_attributes or {}
        data["ISLOCKED"] = self._data.get("ISLOCKED", False)
        data["LOCK_AVAILABLE"] = self._data.get("LOCK_AVAILABLE", False)
        data["BLOCK_HC"] = self._data.get("BLOCK_HC", False)
        return data
