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

from .const import _LOGGER, DOMAIN, ECOBEE_MODEL_TO_NAME, MANUFACTURER

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
    """A humidifier class for an ecobee thermostat with humidifer attached."""

    def __init__(self, data, thermostat_index):
        """Initialize ecobee humidifier platform."""
        self.data = data
        self.thermostat_index = thermostat_index
        self.thermostat = self.data.ecobee.get_thermostat(self.thermostat_index)
        self._name = f"{self.thermostat['name']} Humidifier"
        self._last_humidifier_on_mode = MODE_MANUAL

        self.update_without_throttle = False

    @property
    def name(self):
        """Return the name of the humidifier."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique identifier for the humidifier."""
        return f"{self.data.ecobee.get_thermostat(self.thermostat_index)['identifier']}-humidifier"

    @property
    def device_info(self):
        """Return device information for the ecobee humidifier."""
        thermostat = self.data.ecobee.get_thermostat(self.thermostat_index)
        try:
            model = f"{ECOBEE_MODEL_TO_NAME[thermostat['modelNumber']]} Thermostat"
        except KeyError:
            _LOGGER.error(
                "Model number for ecobee thermostat %s not recognized. "
                "Please visit this link and provide the following information: "
                "https://github.com/home-assistant/core/issues/27172 "
                "Unrecognized model number: %s",
                thermostat["name"],
                thermostat["modelNumber"],
            )
            return None

        return {
            "identifiers": {(DOMAIN, thermostat["identifier"])},
            "name": self.name,
            "manufacturer": MANUFACTURER,
            "model": model,
        }

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

    @property
    def available_modes(self):
        """Return the list of available modes."""
        return [MODE_OFF, MODE_AUTO, MODE_MANUAL]

    @property
    def device_class(self):
        """Return the device class type."""
        return DEVICE_CLASS_HUMIDIFIER

    @property
    def is_on(self):
        """Return True if the humidifier is on."""
        return self.mode != MODE_OFF

    @property
    def max_humidity(self):
        """Return the maximum humidity."""
        return DEFAULT_MAX_HUMIDITY

    @property
    def min_humidity(self):
        """Return the minimum humidity."""
        return DEFAULT_MIN_HUMIDITY

    @property
    def mode(self):
        """Return the current mode, e.g., off, auto, manual."""
        return self.thermostat["settings"]["humidifierMode"]

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_MODES

    @property
    def target_humidity(self) -> int:
        """Return the desired humidity set point."""
        return int(self.thermostat["runtime"]["desiredHumidity"])

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
