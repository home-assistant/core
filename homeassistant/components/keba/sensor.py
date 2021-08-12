"""Support for KEBA charging station sensors."""
from homeassistant.components.sensor import (
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    ELECTRIC_CURRENT_AMPERE,
    ENERGY_KILO_WATT_HOUR,
    POWER_KILO_WATT,
)
from homeassistant.util import dt

from . import DOMAIN


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the KEBA charging station platform."""
    if discovery_info is None:
        return

    keba = hass.data[DOMAIN]

    sensors = [
        KebaSensor(
            keba,
            "max_current",
            SensorEntityDescription(
                key="Curr user",
                name="Max Current",
                native_unit_of_measurement=ELECTRIC_CURRENT_AMPERE,
                device_class=DEVICE_CLASS_CURRENT,
            ),
        ),
        KebaSensor(
            keba,
            "energy_target",
            SensorEntityDescription(
                key="Setenergy",
                name="Energy Target",
                native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
                device_class=DEVICE_CLASS_ENERGY,
            ),
        ),
        KebaSensor(
            keba,
            "charging_power",
            SensorEntityDescription(
                key="P",
                name="Charging Power",
                native_unit_of_measurement=POWER_KILO_WATT,
                device_class=DEVICE_CLASS_POWER,
                state_class=STATE_CLASS_MEASUREMENT,
            ),
        ),
        KebaSensor(
            keba,
            "session_energy",
            SensorEntityDescription(
                key="E pres",
                name="Session Energy",
                native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
                device_class=DEVICE_CLASS_ENERGY,
            ),
        ),
        KebaSensor(
            keba,
            "total_energy",
            SensorEntityDescription(
                key="E total",
                name="Total Energy",
                native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
                device_class=DEVICE_CLASS_ENERGY,
                state_class=STATE_CLASS_MEASUREMENT,
                last_reset=dt.utc_from_timestamp(0),
            ),
        ),
    ]
    async_add_entities(sensors)


class KebaSensor(SensorEntity):
    """The entity class for KEBA charging stations sensors."""

    _attr_should_poll = False

    def __init__(
        self,
        keba,
        entity_type,
        description: SensorEntityDescription,
    ):
        """Initialize the KEBA Sensor."""
        self._keba = keba
        self.entity_description = description
        self._entity_type = entity_type

        self._attr_name = f"{keba.device_name} {description.name}"
        self._attr_unique_id = f"{keba.device_id}_{entity_type}"
        self._attr_icon = description.icon
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        self._attr_device_class = description.device_class
        self._attr_state_class = description.state_class
        self._attr_last_reset = description.last_reset

        self._state = None
        self._attributes: dict[str, str] = {}

    @property
    def should_poll(self):
        """Deactivate polling. Data updated by KebaHandler."""
        return False

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the binary sensor."""
        return self._attributes

    async def async_update(self):
        """Get latest cached states from the device."""
        self._state = self._keba.get_value(self._key)

        if self._key == "P":
            self._attributes["power_factor"] = self._keba.get_value("PF")
            self._attributes["voltage_u1"] = str(self._keba.get_value("U1"))
            self._attributes["voltage_u2"] = str(self._keba.get_value("U2"))
            self._attributes["voltage_u3"] = str(self._keba.get_value("U3"))
            self._attributes["current_i1"] = str(self._keba.get_value("I1"))
            self._attributes["current_i2"] = str(self._keba.get_value("I2"))
            self._attributes["current_i3"] = str(self._keba.get_value("I3"))
        elif self._key == "Curr user":
            self._attributes["max_current_hardware"] = self._keba.get_value("Curr HW")

    def update_callback(self):
        """Schedule a state update."""
        self.async_schedule_update_ha_state(True)

    async def async_added_to_hass(self):
        """Add update callback after being added to hass."""
        self._keba.add_update_listener(self.update_callback)
