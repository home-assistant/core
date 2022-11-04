"""Support gathering ted5000 and ted6000 information."""
import logging

from tedpy import MtuType, SystemType

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    DEVICE_CLASS_ENERGY,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_WATT_HOUR,
    POWER_WATT,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import COORDINATOR, DOMAIN, NAME, OPTION_DEFAULTS

_LOGGER = logging.getLogger(__name__)


def sensors(prefix, stype):
    """Return a list of sensors with given key prefix and type (Production / Consumption)."""
    return [
        SensorEntityDescription(
            key=f"{prefix}_now",
            name=f"Current {stype}",
            native_unit_of_measurement=POWER_WATT,
            state_class=STATE_CLASS_MEASUREMENT,
        ),
        SensorEntityDescription(
            key=f"{prefix}_daily",
            name=f"Today's {stype}",
            native_unit_of_measurement=ENERGY_WATT_HOUR,
            state_class=STATE_CLASS_TOTAL_INCREASING,
            device_class=DEVICE_CLASS_ENERGY,
        ),
        SensorEntityDescription(
            key=f"{prefix}_mtd",
            name=f"Month to Date {stype}",
            native_unit_of_measurement=ENERGY_WATT_HOUR,
            state_class=STATE_CLASS_TOTAL_INCREASING,
            device_class=DEVICE_CLASS_ENERGY,
        ),
    ]


def mtu_sensors(stype):
    """Return a list of mtu sensors with given key prefix and type (Production / Consumption)."""
    return [
        *sensors("mtu_energy", stype),
        SensorEntityDescription(
            key="mtu_power_voltage",
            name="Voltage",
            native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        ),
    ]


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up envoy sensor platform."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = data[COORDINATOR]
    config_name = data[NAME]

    entity_registry = hass.helpers.entity_registry.async_get(hass)
    config_id = config_entry.unique_id
    entities = []
    for desc in sensors("consumption", "Energy Consumption"):
        name = f"{config_name} {desc.name}"
        entities.append(TedSensor(desc, name, config_id, coordinator))

    if coordinator.data["type"] != SystemType.NET:
        for desc in sensors("net", "Net Energy"):
            name = f"{config_name} {desc.name}"
            entities.append(TedSensor(desc, name, config_id, coordinator))
        for desc in sensors("production", "Energy Production"):
            name = f"{config_name} {desc.name}"
            entities.append(TedSensor(desc, name, config_id, coordinator))

    option_entities = []

    for spyder_id, spyder in coordinator.data["spyders"].items():
        spyder_name = spyder["name"]
        for sensor_description in sensors("spyder_energy", "Energy Consumption"):
            entity_name = f"{spyder_name} {sensor_description.name}"
            option_entities.append(
                TedBreakdownSensor(
                    "spyders",
                    spyder_id,
                    sensor_description,
                    entity_name,
                    config_entry.unique_id,
                    coordinator,
                )
            )

    for mtu_id, mtu in coordinator.data["mtus"].items():
        mtu_name = mtu["name"]
        if mtu["type"] == MtuType.LOAD:
            stype = "Energy Consumption"
        elif mtu["type"] == MtuType.GENERATION:
            stype = "Energy Production"
        else:
            stype = "Net Energy"
        for sensor_description in mtu_sensors(stype):
            entity_name = f"{mtu_name} {sensor_description.name}"
            option_entities.append(
                TedBreakdownSensor(
                    "mtus",
                    mtu_id,
                    sensor_description,
                    entity_name,
                    config_entry.unique_id,
                    coordinator,
                )
            )

    for sensor in option_entities:
        option = "show_" + sensor.entity_description.key
        if config_entry.options.get(option, OPTION_DEFAULTS[option]):
            entities.append(sensor)
        else:
            entity_id = entity_registry.async_get_entity_id(
                "sensor", DOMAIN, sensor.unique_id
            )
            if entity_id:
                _LOGGER.debug("Removing entity: %s", sensor.unique_id)
                entity_registry.async_remove(entity_id)

    async_add_entities(entities)
    return True


class TedSensor(CoordinatorEntity, SensorEntity):
    """Implementation of a Ted5000 and Ted6000 sensor."""

    def __init__(self, description, name, device_id, coordinator):
        """Initialize the sensor."""
        self.entity_description = description
        self._device_id = device_id
        self._name = name

        super().__init__(coordinator)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return "mdi:flash"

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return f"{self._device_id}_{self.entity_description.key}"

    @property
    def native_value(self):
        """Return the state of the resources."""
        key, field = self.entity_description.key.split("_")
        return getattr(self.coordinator.data.get(key), field)


class TedBreakdownSensor(TedSensor):
    """Implementation of a Ted5000 and Ted6000 mtu or spyder."""

    def __init__(self, group, position, description, name, device_id, coordinator):
        """Initialize the sensor."""
        self._group = group
        self._position = position
        super().__init__(description, name, device_id, coordinator)

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return f"{self._device_id}_{self._group}_{self._position}_{self.entity_description.key}"

    @property
    def state(self):
        """Return the state of the resources."""
        _, key, field = self.entity_description.key.split("_")
        return getattr(
            self.coordinator.data[self._group].get(self._position).get(key), field
        )
