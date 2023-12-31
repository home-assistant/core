"""Sensors."""
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
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
    hub_name = hass.data[DOMAIN][entry.entry_id]["hub"].name
    _LOGGER.debug("Platformname: %s", hass.data[DOMAIN])
    # hub = hass.data[DOMAIN][hub_name]["hub"]
    hub = hass.data[DOMAIN][entry.entry_id]["hub"]  # Object of class E3DCModbusHub

    sensors = []
    sensor = E3DCSensor(hub_name, hub, "Hersteller", "manufacturer", "W", "mdi:factory")

    sensors.append(sensor)

    # async_add_entities([DemoSensor(hass.data[DOMAIN][entry.entry_id]["hub"])])
    # sensors = [DemoSensor(hub)]
    async_add_entities(sensors, update_before_add=True)


class E3DCSensor(SensorEntity):
    """Representation of an E3DC Modbus sensor.

    Sensor: [Name, Key, Register, Datatype, Count, Unit, Icon]
    """

    # def __init__(self, platform_name, hub, device_info, name, key, unit, icon, register, datatype, count, Scaninterval):
    # def __init__(self, platform_name, hub, device_info, name, key, unit, icon, test=""):
    def __init__(self, platform_name, hub, name, key, unit, icon) -> None:
        """Initialize the sensor."""
        self._platform_name = platform_name
        self._hub = hub
        self._key = key
        self._name = name
        self._register = None
        self._datatype = "datatype"
        self._count = None
        self._scaninterval = 5  # Scaninterval
        self._unit_of_measurement = unit
        self._icon = icon
        self._state = None
        # self._device_info = device_info
        # self._attr_state_class = STATE_CLASS_MEASUREMENT
        # if self._unit_of_measurement == UnitOfEnergy.KILO_WATT_HOUR:
        #    self._attr_state_class = STATE_CLASS_TOTAL_INCREASING
        #    self._attr_device_class = SensorDeviceClass.ENERGY
        #    if (
        #        STATE_CLASS_TOTAL_INCREASING == STATE_CLASS_MEASUREMENT
        #    ):  # compatibility to 2021.8
        #        self._attr_last_reset = dt_util.utc_from_timestamp(0)
        # if self._unit_of_measurement == UnitOfPower.WATT:
        #    self._attr_device_class = SensorDeviceClass.POWER

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self._hub.async_add_e3dc_sensor(self._modbus_data_updated)

    async def async_will_remove_from_hass(self) -> None:
        """Remove Sensors."""
        self._hub.async_remove_e3dc_sensor(self._modbus_data_updated)

    @callback
    def _modbus_data_updated(self):
        self.async_write_ha_state()

    @callback
    def _update_state(self):
        if self._key in self._hub.data:
            self._state = self._hub.data[self._key]

    @property
    def name(self) -> str | None:
        """Return the name."""
        return f"{self._name}"

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return f"{self._platform_name}_{self._key}"

    # @property
    # def unit_of_measurement(self) -> str | None:
    #    """Return the unit of measurement."""
    #    return self._unit_of_measurement

    @property
    def icon(self) -> str | None:
        """Return the sensor icon."""
        return self._icon

    @property
    def register(self) -> int | None:
        """Return the sensor register."""
        return self._register

    @property
    def datatype(self) -> str | None:
        """Return the sensor datatype."""
        return self._datatype

    @property
    def count(self) -> int | None:
        """Return the sensor count."""
        return self._count

    @property
    def scaninterval(self) -> int | None:
        """Return the sensor count."""
        return self._scaninterval

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state
        # if self._key in self._hub.data:
        #    return self._hub.data[self._key]
        # else:
        #    return None

    # @property
    # def extra_state_attributes(self) -> Optional[Mapping[str, Any]]:
    #    """Return extra state attributes based on the sensor key."""
    #    if self._key in ["status", "statusvendor"] and self.state in DEVICE_STATUSSES:
    #        return {ATTR_STATUS_DESCRIPTION: DEVICE_STATUSSES[self.state]}
    #    elif "battery1" in self._key and "battery1_attrs" in self._hub.data:
    #        return self._hub.data["battery1_attrs"]
    #    elif "battery2" in self._key and "battery2_attrs" in self._hub.data:
    #        return self._hub.data["battery2_attrs"]
    #    return None

    @property
    def should_poll(self) -> bool:
        """Data is delivered by the hub."""
        return False

    async def async_update(self) -> None:
        """Aktualisiere den Zustand des Sensors."""
        # Führe hier die Logik durch, um den Zustand des Sensors zu aktualisieren
        self._state = self._hub.get_sensor_data()

    @property
    def device_info(self) -> DeviceInfo:
        """Return default device info."""
        return self._hub.device_info


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
        # self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._device_info = "Geräteinformation Demosensor"
        self._platform_name = "Platform Name -> demnächste Hauskraftwerk"
        self._unit_of_measurement = SensorEntity.unit_of_measurement
        _LOGGER.debug("Sensor: %s", self)

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
