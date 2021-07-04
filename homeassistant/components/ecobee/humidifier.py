"""Support for using humidifier with ecobee thermostats."""
from datetime import timedelta

from homeassistant.components.humidifier import HumidifierEntity
from homeassistant.components.humidifier.const import (
    DEFAULT_MAX_HUMIDITY,
    DEFAULT_MIN_HUMIDITY,
    DEVICE_CLASS_HUMIDIFIER,
    MODE_AUTO,
    SUPPORT_MODES,
)

from .const import DOMAIN, ECOBEE_MODEL_TO_NAME, MANUFACTURER

SCAN_INTERVAL = timedelta(minutes=3)

MODE_MANUAL = "manual"
MODE_OFF = "off"


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the ecobee thermostat humidifier entity."""
    data = hass.data[DOMAIN]
    entities = []
    for index in range(len(data.ecobee.thermostats)):
        thermostat = data.ecobee.get_thermostat(index)
        if thermostat["settings"]["hasHumidifier"]:
            entities.append(EcobeeHumidifier(data, index))

    async_add_entities(entities, True)


class EcobeeHumidifier(HumidifierEntity):
    """A humidifier class for an ecobee thermostat with humidifier attached."""

    _attr_available_modes = [MODE_OFF, MODE_AUTO, MODE_MANUAL]
    _attr_device_class = DEVICE_CLASS_HUMIDIFIER
    _attr_max_humidity = DEFAULT_MAX_HUMIDITY
    _attr_min_humidity = DEFAULT_MIN_HUMIDITY
    _attr_supported_features = SUPPORT_MODES

    def __init__(self, data, thermostat_index):
        """Initialize ecobee humidifier platform."""
        self.data = data
        self.thermostat_index = thermostat_index
        self.thermostat = self.data.ecobee.get_thermostat(self.thermostat_index)
        self._attr_name = self.thermostat["name"]
        self._last_humidifier_on_mode = MODE_MANUAL

        self.update_without_throttle = False
        self._attr_unique_id = f"{self.thermostat['identifier']}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self.thermostat["identifier"])},
            "name": self.name,
            "manufacturer": MANUFACTURER,
            "model": f"{ECOBEE_MODEL_TO_NAME.get(self.thermostat['modelNumber'])} Thermostat",
        }
        self._attr_available = self.thermostat["runtime"]["connected"]
        self._attr_is_on = self.mode != MODE_OFF
        self._attr_mode = self.thermostat["settings"]["humidifierMode"]
        self._attr_target_humidity = int(self.thermostat["runtime"]["desiredHumidity"])

    async def async_update(self):
        """Get the latest state from the thermostat."""
        if self.update_without_throttle:
            await self.data.update(no_throttle=True)
            self.update_without_throttle = False
        else:
            await self.data.update()
        self.thermostat = self.data.ecobee.get_thermostat(self.thermostat_index)
        if self.mode != MODE_OFF:
            self._last_humidifier_on_mode = self.mode

    def set_mode(self, mode):
        """Set humidifier mode (auto, off, manual)."""
        if mode.lower() not in (self.available_modes):
            raise ValueError(
                f"Invalid mode value: {mode}  Valid values are {', '.join(self.available_modes)}."
            )

        self.data.ecobee.set_humidifier_mode(self.thermostat_index, mode)
        self.update_without_throttle = True

    def set_humidity(self, humidity):
        """Set the humidity level."""
        self.data.ecobee.set_humidity(self.thermostat_index, humidity)
        self.update_without_throttle = True

    def turn_off(self, **kwargs):
        """Set humidifier to off mode."""
        self.set_mode(MODE_OFF)

    def turn_on(self, **kwargs):
        """Set humidifier to on mode."""
        self.set_mode(self._last_humidifier_on_mode)
