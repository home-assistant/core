"""Platform for sensor integration."""

from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT, SensorEntity
from homeassistant.const import (
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_VOLTAGE,
    ELECTRIC_CURRENT_AMPERE,
    ELECTRIC_POTENTIAL_VOLT,
    ENERGY_KILO_WATT_HOUR,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    """Config entry example."""
    # objects stored here by __init__.py
    api = hass.data[DOMAIN][entry.entry_id]["api"]
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    uuid = await api.async_get_uuid()

    #
    # Fetch initial data so we have data when entities subscribe
    #
    # If the refresh fails, async_config_entry_first_refresh will
    # raise ConfigEntryNotReady and setup will try again later
    #
    await coordinator.async_config_entry_first_refresh()

    sensors = []
    for twc in coordinator.data:
        for prop in coordinator.data[twc]:
            if prop == "carsCharging":
                sensors.append(TwcSensor(coordinator, uuid, twc, prop, "Cars Charging"))
            if prop == "currentVIN":
                sensors.append(
                    TwcSensor(coordinator, uuid, twc, prop, "Current VIN", False)
                )
            if prop == "lastAmpsOffered":
                sensors.append(
                    CurrentSensor(coordinator, uuid, twc, prop, "Last Amps Offered")
                )
            if prop == "lastVIN":
                sensors.append(
                    TwcSensor(coordinator, uuid, twc, prop, "Last VIN", False)
                )
            if prop == "lifetimekWh":
                sensors.append(
                    EnergySensor(coordinator, uuid, twc, prop, "Lifetime Energy")
                )
            if prop == "maxAmps":
                sensors.append(CurrentSensor(coordinator, uuid, twc, prop, "Max Amps"))
            if prop == "reportedAmpsActual":
                sensors.append(
                    CurrentSensor(coordinator, uuid, twc, prop, "Reported Amps")
                )
            if prop == "state":
                sensors.append(TwcSensor(coordinator, uuid, twc, prop, "State", False))
            if prop == "version":
                sensors.append(
                    TwcSensor(coordinator, uuid, twc, prop, "Version", False)
                )
            if prop == "voltsPhaseA":
                sensors.append(
                    VoltageSensor(coordinator, uuid, twc, prop, "Voltage (Phase A)")
                )
            if prop == "voltsPhaseB":
                sensors.append(
                    VoltageSensor(coordinator, uuid, twc, prop, "Voltage (Phase B)")
                )
            if prop == "voltsPhaseC":
                sensors.append(
                    VoltageSensor(coordinator, uuid, twc, prop, "Voltage (Phase C)")
                )

    async_add_entities(sensors)


class TwcSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Sensor."""

    def __init__(self, coordinator, uuid, twc, prop, name, isMeasurement=True):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self._twc = twc
        self._prop = prop
        self._attr_unique_id = uuid + "-" + twc + "-" + prop
        self._attr_name = "TWC " + str(twc).capitalize() + " " + name
        if isMeasurement:
            self._attr_state_class = STATE_CLASS_MEASUREMENT

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.coordinator.data[self._twc][self._prop]


class CurrentSensor(TwcSensor):
    """Representation of a Sensor that measures current."""

    def __init__(self, coordinator, uuid, twc, prop, name):
        """Pass coordinator, uuid, twc, prop and name to TwcSensor."""
        super().__init__(coordinator, uuid, twc, prop, name)
        self._attr_unit_of_measurement = ELECTRIC_CURRENT_AMPERE
        self._attr_device_class = DEVICE_CLASS_CURRENT


class VoltageSensor(TwcSensor):
    """Representation of a Sensor that measures volage."""

    def __init__(self, coordinator, uuid, twc, prop, name):
        """Pass coordinator, uuid, twc, prop and name to TwcSensor."""
        super().__init__(coordinator, uuid, twc, prop, name)
        self._attr_unit_of_measurement = ELECTRIC_POTENTIAL_VOLT
        self._attr_device_class = DEVICE_CLASS_VOLTAGE


class EnergySensor(TwcSensor):
    """Representation of a Sensor that measures energy."""

    def __init__(self, coordinator, uuid, twc, prop, name):
        """Pass coordinator, uuid, twc, prop and name to TwcSensor."""
        super().__init__(coordinator, uuid, twc, prop, name)
        self._attr_unit_of_measurement = ENERGY_KILO_WATT_HOUR
        self._attr_device_class = DEVICE_CLASS_ENERGY
