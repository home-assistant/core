"""Support for monitoring a Sense energy sensor."""
from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT, SensorEntity
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    DEVICE_CLASS_POWER,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
    VOLT,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

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
    SENSE_TRENDS_COORDINATOR,
)


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
    trends_coordinator = hass.data[DOMAIN][config_entry.entry_id][
        SENSE_TRENDS_COORDINATOR
    ]

    # Request only in case it takes longer
    # than 60s
    await trends_coordinator.async_request_refresh()

    sense_monitor_id = data.sense_monitor_id
    sense_devices = hass.data[DOMAIN][config_entry.entry_id][
        SENSE_DISCOVERED_DEVICES_DATA
    ]

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

    for i in range(len(data.active_voltage)):
        devices.append(SenseVoltageSensor(data, i, sense_monitor_id))

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
                    trends_coordinator,
                    unique_id,
                )
            )

    async_add_entities(devices)


class SenseActiveSensor(SensorEntity):
    """Implementation of a Sense energy sensor."""

    _attr_icon = ICON
    _attr_unit_of_measurement = POWER_WATT
    _attr_extra_state_attributes = {ATTR_ATTRIBUTION: ATTRIBUTION}
    _attr_should_poll = False
    _attr_available = False
    _attr_state_class = STATE_CLASS_MEASUREMENT

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
        self._attr_name = f"{name} {name_type}"
        self._attr_unique_id = unique_id
        self._data = data
        self._sense_monitor_id = sense_monitor_id
        self._sensor_type = sensor_type
        self._is_production = is_production

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SENSE_DEVICE_UPDATE}-{self._sense_monitor_id}",
                self._async_update_from_data,
            )
        )

    @callback
    def _async_update_from_data(self):
        """Update the sensor from the data. Must not do I/O."""
        new_state = round(
            self._data.active_solar_power
            if self._is_production
            else self._data.active_power
        )
        if self._attr_available and self._attr_state == new_state:
            return
        self._attr_state = new_state
        self._attr_available = True
        self.async_write_ha_state()


class SenseVoltageSensor(SensorEntity):
    """Implementation of a Sense energy voltage sensor."""

    _attr_unit_of_measurement = VOLT
    _attr_extra_state_attributes = {ATTR_ATTRIBUTION: ATTRIBUTION}
    _attr_icon = ICON
    _attr_should_poll = False
    _attr_available = False

    def __init__(
        self,
        data,
        index,
        sense_monitor_id,
    ):
        """Initialize the Sense sensor."""
        line_num = index + 1
        self._attr_name = f"L{line_num} Voltage"
        self._attr_unique_id = f"{sense_monitor_id}-L{line_num}"
        self._data = data
        self._sense_monitor_id = sense_monitor_id
        self._voltage_index = index

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SENSE_DEVICE_UPDATE}-{self._sense_monitor_id}",
                self._async_update_from_data,
            )
        )

    @callback
    def _async_update_from_data(self):
        """Update the sensor from the data. Must not do I/O."""
        new_state = round(self._data.active_voltage[self._voltage_index], 1)
        if self._attr_available and self._attr_state == new_state:
            return
        self._attr_available = True
        self._attr_state = new_state
        self.async_write_ha_state()


class SenseTrendsSensor(SensorEntity):
    """Implementation of a Sense energy sensor."""

    _attr_unit_of_measurement = ENERGY_KILO_WATT_HOUR
    _attr_extra_state_attributes = {ATTR_ATTRIBUTION: ATTRIBUTION}
    _attr_icon = ICON
    _attr_should_poll = False

    def __init__(
        self,
        data,
        name,
        sensor_type,
        is_production,
        trends_coordinator,
        unique_id,
    ):
        """Initialize the Sense sensor."""
        name_type = PRODUCTION_NAME if is_production else CONSUMPTION_NAME
        self._attr_name = f"{name} {name_type}"
        self._attr_unique_id = unique_id
        self._data = data
        self._sensor_type = sensor_type
        self._coordinator = trends_coordinator
        self._is_production = is_production
        self._had_any_update = False

    @property
    def state(self):
        """Return the state of the sensor."""
        return round(self._data.get_trend(self._sensor_type, self._is_production), 1)

    @property
    def available(self):
        """Return if entity is available."""
        return self._had_any_update and self._coordinator.last_update_success

    @callback
    def _async_update(self):
        """Track if we had an update so we do not report zero data."""
        self._had_any_update = True
        self.async_write_ha_state()

    async def async_update(self):
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self._coordinator.async_request_refresh()

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(self._coordinator.async_add_listener(self._async_update))


class SenseEnergyDevice(SensorEntity):
    """Implementation of a Sense energy device."""

    _attr_available = False
    _attr_state_class = STATE_CLASS_MEASUREMENT
    _attr_unit_of_measurement = POWER_WATT
    _attr_extra_state_attributes = {ATTR_ATTRIBUTION: ATTRIBUTION}
    _attr_device_class = DEVICE_CLASS_POWER
    _attr_should_poll = False

    def __init__(self, sense_devices_data, device, sense_monitor_id):
        """Initialize the Sense binary sensor."""
        self._attr_name = f"{device['name']} {CONSUMPTION_NAME}"
        self._id = device["id"]
        self._sense_monitor_id = sense_monitor_id
        self._attr_unique_id = f"{sense_monitor_id}-{self._id}-{CONSUMPTION_ID}"
        self._attr_icon = sense_to_mdi(device["icon"])
        self._sense_devices_data = sense_devices_data

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SENSE_DEVICE_UPDATE}-{self._sense_monitor_id}",
                self._async_update_from_data,
            )
        )

    @callback
    def _async_update_from_data(self):
        """Get the latest data, update state. Must not do I/O."""
        device_data = self._sense_devices_data.get_device_by_id(self._id)
        if not device_data or "w" not in device_data:
            new_state = 0
        else:
            new_state = int(device_data["w"])
        if self._attr_available and self._attr_state == new_state:
            return
        self._attr_state = new_state
        self._attr_available = True
        self.async_write_ha_state()
