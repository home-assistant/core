"""Support for Homekit sensors."""
import enum
import logging

from aiohomekit.model.characteristics import CharacteristicsTypes

from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_STATELESS_PROGRAMMABLE_SWITCH,
    DEVICE_CLASS_TEMPERATURE,
    TEMP_CELSIUS,
    UNIT_PERCENTAGE,
)
from homeassistant.core import callback

from . import KNOWN_DEVICES, HomeKitEntity

HUMIDITY_ICON = "mdi:water-percent"
TEMP_C_ICON = "mdi:thermometer"
BRIGHTNESS_ICON = "mdi:brightness-6"
CO2_ICON = "mdi:molecule-co2"

UNIT_LUX = "lux"

_LOGGER = logging.getLogger(__name__)


class HomeKitHumiditySensor(HomeKitEntity):
    """Representation of a Homekit humidity sensor."""

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT]

    @property
    def device_class(self) -> str:
        """Return the device class of the sensor."""
        return DEVICE_CLASS_HUMIDITY

    @property
    def name(self):
        """Return the name of the device."""
        return f"{super().name} Humidity"

    @property
    def icon(self):
        """Return the sensor icon."""
        return HUMIDITY_ICON

    @property
    def unit_of_measurement(self):
        """Return units for the sensor."""
        return UNIT_PERCENTAGE

    @property
    def state(self):
        """Return the current humidity."""
        return self.service.value(CharacteristicsTypes.RELATIVE_HUMIDITY_CURRENT)


class HomeKitTemperatureSensor(HomeKitEntity):
    """Representation of a Homekit temperature sensor."""

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.TEMPERATURE_CURRENT]

    @property
    def device_class(self) -> str:
        """Return the device class of the sensor."""
        return DEVICE_CLASS_TEMPERATURE

    @property
    def name(self):
        """Return the name of the device."""
        return f"{super().name} Temperature"

    @property
    def icon(self):
        """Return the sensor icon."""
        return TEMP_C_ICON

    @property
    def unit_of_measurement(self):
        """Return units for the sensor."""
        return TEMP_CELSIUS

    @property
    def state(self):
        """Return the current temperature in Celsius."""
        return self.service.value(CharacteristicsTypes.TEMPERATURE_CURRENT)


class HomeKitLightSensor(HomeKitEntity):
    """Representation of a Homekit light level sensor."""

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.LIGHT_LEVEL_CURRENT]

    @property
    def device_class(self) -> str:
        """Return the device class of the sensor."""
        return DEVICE_CLASS_ILLUMINANCE

    @property
    def name(self):
        """Return the name of the device."""
        return f"{super().name} Light Level"

    @property
    def icon(self):
        """Return the sensor icon."""
        return BRIGHTNESS_ICON

    @property
    def unit_of_measurement(self):
        """Return units for the sensor."""
        return UNIT_LUX

    @property
    def state(self):
        """Return the current light level in lux."""
        return self.service.value(CharacteristicsTypes.LIGHT_LEVEL_CURRENT)


class HomeKitCarbonDioxideSensor(HomeKitEntity):
    """Representation of a Homekit Carbon Dioxide sensor."""

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        return [CharacteristicsTypes.CARBON_DIOXIDE_LEVEL]

    @property
    def name(self):
        """Return the name of the device."""
        return f"{super().name} CO2"

    @property
    def icon(self):
        """Return the sensor icon."""
        return CO2_ICON

    @property
    def unit_of_measurement(self):
        """Return units for the sensor."""
        return CONCENTRATION_PARTS_PER_MILLION

    @property
    def state(self):
        """Return the current CO2 level in ppm."""
        return self.service.value(CharacteristicsTypes.CARBON_DIOXIDE_LEVEL)


class HomeKitBatterySensor(HomeKitEntity):
    """Representation of a Homekit battery sensor."""

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        return [
            CharacteristicsTypes.BATTERY_LEVEL,
            CharacteristicsTypes.STATUS_LO_BATT,
            CharacteristicsTypes.CHARGING_STATE,
        ]

    @property
    def device_class(self) -> str:
        """Return the device class of the sensor."""
        return DEVICE_CLASS_BATTERY

    @property
    def name(self):
        """Return the name of the device."""
        return f"{super().name} Battery"

    @property
    def icon(self):
        """Return the sensor icon."""
        if not self.available or self.state is None:
            return "mdi:battery-unknown"

        # This is similar to the logic in helpers.icon, but we have delegated the
        # decision about what mdi:battery-alert is to the device.
        icon = "mdi:battery"
        if self.is_charging and self.state > 10:
            percentage = int(round(self.state / 20 - 0.01)) * 20
            icon += f"-charging-{percentage}"
        elif self.is_charging:
            icon += "-outline"
        elif self.is_low_battery:
            icon += "-alert"
        elif self.state < 95:
            percentage = max(int(round(self.state / 10 - 0.01)) * 10, 10)
            icon += f"-{percentage}"

        return icon

    @property
    def unit_of_measurement(self):
        """Return units for the sensor."""
        return UNIT_PERCENTAGE

    @property
    def is_low_battery(self):
        """Return true if battery level is low."""
        return self.service.value(CharacteristicsTypes.STATUS_LO_BATT) == 1

    @property
    def is_charging(self):
        """Return true if currently charing."""
        # 0 = not charging
        # 1 = charging
        # 2 = not chargeable
        return self.service.value(CharacteristicsTypes.CHARGING_STATE) == 1

    @property
    def state(self):
        """Return the current battery level percentage."""
        return self.service.value(CharacteristicsTypes.BATTERY_LEVEL)


class InputEvents(enum.IntEnum):
    """Input event values that a stateless programmable switch can be."""

    SINGLE_PRESS = 0
    DOUBLE_PRESS = 1
    LONG_PRESS = 2


STATELESS_PROGRAMMABLE_SWITCH_INPUT_EVENT_HOMEKIT_TO_HASS = {
    None: "released",
    InputEvents.SINGLE_PRESS: "single_pressed",
    InputEvents.DOUBLE_PRESS: "double_pressed",
    InputEvents.LONG_PRESS: "long_pressed",
}


class HomeKitStatelessProgrammableSwitch(HomeKitEntity):
    """Representation of a Homekit Stateless Programmable Switch."""

    def __init__(self, accessory, devinfo):
        """Initialise a generic HomeKit device."""
        super().__init__(accessory, devinfo)
        self.last_input_event = None

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        return [
            CharacteristicsTypes.INPUT_EVENT,
        ]

    @property
    def state(self):
        """Return the state of the binary sensor."""
        input_event = self.service.value(CharacteristicsTypes.INPUT_EVENT)
        _LOGGER.info("entity=%s, new=%s", self.entity_id, input_event)
        hass_input_event = STATELESS_PROGRAMMABLE_SWITCH_INPUT_EVENT_HOMEKIT_TO_HASS.get(
            input_event
        )
        if not (
            hass_input_event == "released" and self.last_input_event == "released"
        ):  # avoid repeated "released" events
            if hass_input_event:
                self.hass.bus.fire(
                    "sensor.stateless_programmable_switch.pressed",
                    {"entity_id": self.entity_id, "input_event": hass_input_event},
                )
                self.last_input_event = hass_input_event
            else:
                _LOGGER.warning(
                    "HomeKit device %s: Input event value %s is not supported yet."
                    " Consider raising a ticket if you have this device and want to help us implement this feature.",
                    self.entity_id,
                    input_event,
                )
        return hass_input_event

    @property
    def device_class(self) -> str:
        """Return the device class of the sensor."""
        return DEVICE_CLASS_STATELESS_PROGRAMMABLE_SWITCH


ENTITY_TYPES = {
    "humidity": HomeKitHumiditySensor,
    "temperature": HomeKitTemperatureSensor,
    "light": HomeKitLightSensor,
    "carbon-dioxide": HomeKitCarbonDioxideSensor,
    "battery": HomeKitBatterySensor,
    "stateless-programmable-switch": HomeKitStatelessProgrammableSwitch,
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Homekit sensors."""
    hkid = config_entry.data["AccessoryPairingID"]
    conn = hass.data[KNOWN_DEVICES][hkid]

    @callback
    def async_add_service(aid, service):
        entity_class = ENTITY_TYPES.get(service["stype"])
        if not entity_class:
            return False
        info = {"aid": aid, "iid": service["iid"]}
        async_add_entities([entity_class(conn, info)], True)
        return True

    conn.add_listener(async_add_service)
