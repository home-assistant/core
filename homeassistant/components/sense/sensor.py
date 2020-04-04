"""Support for monitoring a Sense energy sensor."""
from datetime import timedelta
import logging

from homeassistant.const import (
    ATTR_ATTRIBUTION,
    DEVICE_CLASS_POWER,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

from .const import (
    ACTIVE_NAME,
    ACTIVE_TYPE,
    ATTRIBUTION,
    CONSUMPTION_ID,
    CONSUMPTION_NAME,
    DOMAIN,
    ICON,
    MDI_ICONS,
    PRODUCTION_ID,
    PRODUCTION_NAME,
    SENSE_DATA,
    SENSE_DEVICE_UPDATE,
    SENSE_DEVICES_DATA,
    SENSE_DISCOVERED_DEVICES_DATA,
    SENSE_TIMEOUT_EXCEPTIONS,
)

MIN_TIME_BETWEEN_DAILY_UPDATES = timedelta(seconds=300)


_LOGGER = logging.getLogger(__name__)


class SensorConfig:
    """Data structure holding sensor configuration."""

    def __init__(self, name, sensor_type):
        """Sensor name and type to pass to API."""
        self.name = name
        self.sensor_type = sensor_type


# Sensor types/ranges
ACTIVE_SENSOR_TYPE = SensorConfig(ACTIVE_NAME, ACTIVE_TYPE)

# Sensor types/ranges
TRENDS_SENSOR_TYPES = {
    "daily": SensorConfig("Daily", "DAY"),
    "weekly": SensorConfig("Weekly", "WEEK"),
    "monthly": SensorConfig("Monthly", "MONTH"),
    "yearly": SensorConfig("Yearly", "YEAR"),
}

# Production/consumption variants
SENSOR_VARIANTS = [PRODUCTION_ID, CONSUMPTION_ID]


def sense_to_mdi(sense_icon):
    """Convert sense icon to mdi icon."""
    return "mdi:{}".format(MDI_ICONS.get(sense_icon, "power-plug"))


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Sense sensor."""
    data = hass.data[DOMAIN][config_entry.entry_id][SENSE_DATA]
    sense_devices_data = hass.data[DOMAIN][config_entry.entry_id][SENSE_DEVICES_DATA]

    @Throttle(MIN_TIME_BETWEEN_DAILY_UPDATES)
    async def update_trends():
        """Update the daily power usage."""
        await data.update_trend_data()

    sense_monitor_id = data.sense_monitor_id
    sense_devices = hass.data[DOMAIN][config_entry.entry_id][
        SENSE_DISCOVERED_DEVICES_DATA
    ]
    await data.update_trend_data()

    devices = [
        SenseEnergyDevice(sense_devices_data, device, sense_monitor_id)
        for device in sense_devices
        if device["tags"]["DeviceListAllowed"] == "true"
    ]

    for var in SENSOR_VARIANTS:
        name = ACTIVE_SENSOR_TYPE.name
        sensor_type = ACTIVE_SENSOR_TYPE.sensor_type
        is_production = var == PRODUCTION_ID

        unique_id = f"{sense_monitor_id}-active-{var}"
        devices.append(
            SenseActiveSensor(
                data, name, sensor_type, is_production, sense_monitor_id, var, unique_id
            )
        )

    for type_id in TRENDS_SENSOR_TYPES:
        typ = TRENDS_SENSOR_TYPES[type_id]
        for var in SENSOR_VARIANTS:
            name = typ.name
            sensor_type = typ.sensor_type
            is_production = var == PRODUCTION_ID

            unique_id = f"{sense_monitor_id}-{type_id}-{var}"
            devices.append(
                SenseTrendsSensor(
                    data,
                    name,
                    sensor_type,
                    is_production,
                    update_trends,
                    var,
                    unique_id,
                )
            )

    async_add_entities(devices)


class SenseActiveSensor(Entity):
    """Implementation of a Sense energy sensor."""

    def __init__(
        self,
        data,
        name,
        sensor_type,
        is_production,
        sense_monitor_id,
        sensor_id,
        unique_id,
    ):
        """Initialize the Sense sensor."""
        name_type = PRODUCTION_NAME if is_production else CONSUMPTION_NAME
        self._name = f"{name} {name_type}"
        self._unique_id = unique_id
        self._available = False
        self._data = data
        self._sense_monitor_id = sense_monitor_id
        self._sensor_type = sensor_type
        self._is_production = is_production
        self._state = None
        self._undo_dispatch_subscription = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def available(self):
        """Return the availability of the sensor."""
        return self._available

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return POWER_WATT

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {ATTR_ATTRIBUTION: ATTRIBUTION}

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._unique_id

    @property
    def should_poll(self):
        """Return the device should not poll for updates."""
        return False

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._undo_dispatch_subscription = async_dispatcher_connect(
            self.hass,
            f"{SENSE_DEVICE_UPDATE}-{self._sense_monitor_id}",
            self._async_update_from_data,
        )

    async def async_will_remove_from_hass(self):
        """Undo subscription."""
        if self._undo_dispatch_subscription:
            self._undo_dispatch_subscription()

    @callback
    def _async_update_from_data(self):
        """Update the sensor from the data. Must not do I/O."""
        self._state = round(
            self._data.active_solar_power
            if self._is_production
            else self._data.active_power
        )
        self._available = True
        self.async_write_ha_state()


class SenseTrendsSensor(Entity):
    """Implementation of a Sense energy sensor."""

    def __init__(
        self, data, name, sensor_type, is_production, update_call, sensor_id, unique_id
    ):
        """Initialize the Sense sensor."""
        name_type = PRODUCTION_NAME if is_production else CONSUMPTION_NAME
        self._name = f"{name} {name_type}"
        self._unique_id = unique_id
        self._available = False
        self._data = data
        self._sensor_type = sensor_type
        self.update_sensor = update_call
        self._is_production = is_production
        self._state = None
        self._unit_of_measurement = ENERGY_KILO_WATT_HOUR

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def available(self):
        """Return the availability of the sensor."""
        return self._available

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    @property
    def unique_id(self):
        """Return the unique id."""
        return self._unique_id

    async def async_update(self):
        """Get the latest data, update state."""

        try:
            await self.update_sensor()
        except SENSE_TIMEOUT_EXCEPTIONS:
            _LOGGER.error("Timeout retrieving data")
            return

        state = self._data.get_trend(self._sensor_type, self._is_production)
        self._state = round(state, 1)
        self._available = True


class SenseEnergyDevice(Entity):
    """Implementation of a Sense energy device."""

    def __init__(self, sense_devices_data, device, sense_monitor_id):
        """Initialize the Sense binary sensor."""
        self._name = f"{device['name']} {CONSUMPTION_NAME}"
        self._id = device["id"]
        self._available = False
        self._sense_monitor_id = sense_monitor_id
        self._unique_id = f"{sense_monitor_id}-{self._id}-{CONSUMPTION_ID}"
        self._icon = sense_to_mdi(device["icon"])
        self._sense_devices_data = sense_devices_data
        self._undo_dispatch_subscription = None
        self._state = None

    @property
    def state(self):
        """Return the wattage of the sensor."""
        return self._state

    @property
    def available(self):
        """Return the availability of the sensor."""
        return self._available

    @property
    def name(self):
        """Return the name of the power sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id of the power sensor."""
        return self._unique_id

    @property
    def icon(self):
        """Return the icon of the power sensor."""
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return POWER_WATT

    @property
    def device_class(self):
        """Return the device class of the power sensor."""
        return DEVICE_CLASS_POWER

    @property
    def should_poll(self):
        """Return the device should not poll for updates."""
        return False

    async def async_added_to_hass(self):
        """Register callbacks."""
        self._undo_dispatch_subscription = async_dispatcher_connect(
            self.hass,
            f"{SENSE_DEVICE_UPDATE}-{self._sense_monitor_id}",
            self._async_update_from_data,
        )

    async def async_will_remove_from_hass(self):
        """Undo subscription."""
        if self._undo_dispatch_subscription:
            self._undo_dispatch_subscription()

    @callback
    def _async_update_from_data(self):
        """Get the latest data, update state. Must not do I/O."""
        device_data = self._sense_devices_data.get_device_by_id(self._id)
        if not device_data or "w" not in device_data:
            self._state = 0
        else:
            self._state = int(device_data["w"])
        self._available = True
        self.async_write_ha_state()
