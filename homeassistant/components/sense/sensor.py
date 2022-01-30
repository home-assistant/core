"""Support for monitoring a Sense energy sensor."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
    PERCENTAGE,
    POWER_WATT,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ACTIVE_NAME,
    ACTIVE_TYPE,
    ATTRIBUTION,
    CONSUMPTION_ID,
    CONSUMPTION_NAME,
    DOMAIN,
    FROM_GRID_ID,
    FROM_GRID_NAME,
    ICON,
    MDI_ICONS,
    NET_PRODUCTION_ID,
    NET_PRODUCTION_NAME,
    PRODUCTION_ID,
    PRODUCTION_NAME,
    PRODUCTION_PCT_ID,
    PRODUCTION_PCT_NAME,
    SENSE_DATA,
    SENSE_DEVICE_UPDATE,
    SENSE_DEVICES_DATA,
    SENSE_DISCOVERED_DEVICES_DATA,
    SENSE_TRENDS_COORDINATOR,
    SOLAR_POWERED_ID,
    SOLAR_POWERED_NAME,
    TO_GRID_ID,
    TO_GRID_NAME,
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
SENSOR_VARIANTS = [(PRODUCTION_ID, PRODUCTION_NAME), (CONSUMPTION_ID, CONSUMPTION_NAME)]

# Trend production/consumption variants
TREND_SENSOR_VARIANTS = SENSOR_VARIANTS + [
    (PRODUCTION_PCT_ID, PRODUCTION_PCT_NAME),
    (NET_PRODUCTION_ID, NET_PRODUCTION_NAME),
    (FROM_GRID_ID, FROM_GRID_NAME),
    (TO_GRID_ID, TO_GRID_NAME),
    (SOLAR_POWERED_ID, SOLAR_POWERED_NAME),
]


def sense_to_mdi(sense_icon):
    """Convert sense icon to mdi icon."""
    return "mdi:{}".format(MDI_ICONS.get(sense_icon, "power-plug"))


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Sense sensor."""
    base_data = hass.data[DOMAIN][config_entry.entry_id]
    data = base_data[SENSE_DATA]
    sense_devices_data = base_data[SENSE_DEVICES_DATA]
    trends_coordinator = base_data[SENSE_TRENDS_COORDINATOR]

    # Request only in case it takes longer
    # than 60s
    await trends_coordinator.async_request_refresh()

    sense_monitor_id = data.sense_monitor_id
    sense_devices = hass.data[DOMAIN][config_entry.entry_id][
        SENSE_DISCOVERED_DEVICES_DATA
    ]

    entities: list[SensorEntity] = [
        SenseEnergyDevice(sense_devices_data, device, sense_monitor_id)
        for device in sense_devices
        if device["tags"]["DeviceListAllowed"] == "true"
    ]

    for variant_id, variant_name in SENSOR_VARIANTS:
        name = ACTIVE_SENSOR_TYPE.name
        sensor_type = ACTIVE_SENSOR_TYPE.sensor_type

        unique_id = f"{sense_monitor_id}-active-{variant_id}"
        entities.append(
            SenseActiveSensor(
                data,
                name,
                sensor_type,
                sense_monitor_id,
                variant_id,
                variant_name,
                unique_id,
            )
        )

    for i in range(len(data.active_voltage)):
        entities.append(SenseVoltageSensor(data, i, sense_monitor_id))

    for type_id, typ in TRENDS_SENSOR_TYPES.items():
        for variant_id, variant_name in TREND_SENSOR_VARIANTS:
            name = typ.name
            sensor_type = typ.sensor_type

            unique_id = f"{sense_monitor_id}-{type_id}-{variant_id}"
            entities.append(
                SenseTrendsSensor(
                    data,
                    name,
                    sensor_type,
                    variant_id,
                    variant_name,
                    trends_coordinator,
                    unique_id,
                    sense_monitor_id,
                )
            )

    async_add_entities(entities)


class SenseActiveSensor(SensorEntity):
    """Implementation of a Sense energy sensor."""

    _attr_icon = ICON
    _attr_native_unit_of_measurement = POWER_WATT
    _attr_attribution = ATTRIBUTION
    _attr_should_poll = False
    _attr_available = False
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        data,
        name,
        sensor_type,
        sense_monitor_id,
        variant_id,
        variant_name,
        unique_id,
    ):
        """Initialize the Sense sensor."""
        self._attr_name = f"{name} {variant_name}"
        self._attr_unique_id = unique_id
        self._data = data
        self._sense_monitor_id = sense_monitor_id
        self._sensor_type = sensor_type
        self._variant_id = variant_id
        self._variant_name = variant_name

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
            if self._variant_id == PRODUCTION_ID
            else self._data.active_power
        )
        if self._attr_available and self._attr_native_value == new_state:
            return
        self._attr_native_value = new_state
        self._attr_available = True
        self.async_write_ha_state()


class SenseVoltageSensor(SensorEntity):
    """Implementation of a Sense energy voltage sensor."""

    _attr_native_unit_of_measurement = ELECTRIC_POTENTIAL_VOLT
    _attr_attribution = ATTRIBUTION
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
        if self._attr_available and self._attr_native_value == new_state:
            return
        self._attr_available = True
        self._attr_native_value = new_state
        self.async_write_ha_state()


class SenseTrendsSensor(CoordinatorEntity, SensorEntity):
    """Implementation of a Sense energy sensor."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = ENERGY_KILO_WATT_HOUR
    _attr_attribution = ATTRIBUTION
    _attr_icon = ICON
    _attr_should_poll = False

    def __init__(
        self,
        data,
        name,
        sensor_type,
        variant_id,
        variant_name,
        trends_coordinator,
        unique_id,
        sense_monitor_id,
    ):
        """Initialize the Sense sensor."""
        super().__init__(trends_coordinator)
        self._attr_name = f"{name} {variant_name}"
        self._attr_unique_id = unique_id
        self._data = data
        self._sensor_type = sensor_type
        self._variant_id = variant_id
        self._had_any_update = False
        if variant_id in [PRODUCTION_PCT_ID, SOLAR_POWERED_ID]:
            self._attr_native_unit_of_measurement = PERCENTAGE
            self._attr_entity_registry_enabled_default = False
            self._attr_state_class = None
            self._attr_device_class = None
        self._attr_device_info = DeviceInfo(
            name=f"Sense {sense_monitor_id}",
            identifiers={(DOMAIN, sense_monitor_id)},
            model="Sense",
            manufacturer="Sense Labs, Inc.",
            configuration_url="https://home.sense.com",
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return round(self._data.get_trend(self._sensor_type, self._variant_id), 1)

    @property
    def last_reset(self):
        """Return the time when the sensor was last reset, if any."""
        return self._data.trend_start(self._sensor_type)


class SenseEnergyDevice(SensorEntity):
    """Implementation of a Sense energy device."""

    _attr_available = False
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = POWER_WATT
    _attr_attribution = ATTRIBUTION
    _attr_device_class = SensorDeviceClass.POWER
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
        if self._attr_available and self._attr_native_value == new_state:
            return
        self._attr_native_value = new_state
        self._attr_available = True
        self.async_write_ha_state()
