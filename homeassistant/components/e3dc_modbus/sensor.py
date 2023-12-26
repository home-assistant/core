"""Sensors."""
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# async def async_setup_entry(
#    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
# ) -> None:
#    """Initialisieren."""
#    # hub_name = entry.data[CONF_NAME]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensor platform."""
    async_add_entities([DemoSensor(hass.data[DOMAIN][entry.entry_id]["hub"])])
    # sensors = [DemoSensor(hub)]
    # async_add_entities(sensors, update_before_add=True)


class DemoSensor(SensorEntity):
    """Representation of a Demo Sensor."""

    def __init__(self, hub) -> None:
        """Initialize the sensor."""
        self._hub = hub
        self._state = 23.6  # You can set this to any value you want
        self._attr_unique_id = f"{hub.name}_demo_sensor_id"
        self._attr_name = f"{hub.name} Demo Sensor Name"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        # self._attr_unit_of_measurement = SensorEntity.unit_of_measurement
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._device_info = "Geräteinformation"
        self._platform_name = "Platform Name"
        # self._unit_of_measurement = SensorEntity.unit_of_measurement
        _LOGGER.debug("Device info: %s", self.device_info)

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self._hub.async_add_e3dc_sensor(self._modbus_data_updated)

    async def async_will_remove_from_hass(self) -> None:
        """Remove Sensors."""
        self._hub.async_remove_e3dc_sensor(self._modbus_data_updated)

    @callback
    def _modbus_data_updated(self) -> None:
        self.async_write_ha_state()

    @property
    def name(self) -> str:
        """Return the name."""
        return f"{self._attr_name}"

    # @property
    # def state(self) -> float:
    #    """Return the state of the sensor."""
    #    return self._state

    @property
    def should_poll(self) -> bool:
        """Disable polling for this sensor since it's value is fixed."""
        return False

    # @property
    # def device_info(self):
    #    """Get Device Info.

    #    Returns:
    #        dict: A dictionary containing the device information.
    #            - identifiers: A set of identifiers for the device.
    #            - name: The name of the device.
    #            - manufacturer: The manufacturer of the device.
    #            - model: The model of the device.
    #    """
    #    return {
    #        "identifiers": {(DOMAIN, self._hub.name)},
    #        "name": self._hub.name,
    #        "manufacturer": "E3/DC Hager AG",
    #        "model": "S10E Pro",
    #    }

    # @property
    # def device_info(self) -> Optional[Dict[str, Any]]:
    #    return self._device_info
