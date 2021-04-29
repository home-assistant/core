"""Support for AVM Fritz!Box smarthome temperature sensor only devices."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    DEVICE_CLASS_BATTERY,
    PERCENTAGE,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FritzBoxEntity
from .const import (
    ATTR_STATE_DEVICE_LOCKED,
    ATTR_STATE_LOCKED,
    CONF_COORDINATOR,
    DOMAIN as FRITZBOX_DOMAIN,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the FRITZ!SmartHome sensor from ConfigEntry."""
    entities = []
    coordinator = hass.data[FRITZBOX_DOMAIN][entry.entry_id][CONF_COORDINATOR]

    for ain, device in coordinator.data.items():
        if (
            device.has_temperature_sensor
            and not device.has_switch
            and not device.has_thermostat
        ):
            entities.append(
                FritzBoxTempSensor(
                    {
                        ATTR_NAME: f"{device.name}",
                        ATTR_ENTITY_ID: f"{device.ain}",
                        ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
                        ATTR_DEVICE_CLASS: None,
                    },
                    coordinator,
                    ain,
                )
            )

        if device.battery_level is not None:
            entities.append(
                FritzBoxBatterySensor(
                    {
                        ATTR_NAME: f"{device.name} Battery",
                        ATTR_ENTITY_ID: f"{device.ain}_battery",
                        ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
                        ATTR_DEVICE_CLASS: DEVICE_CLASS_BATTERY,
                    },
                    coordinator,
                    ain,
                )
            )

    async_add_entities(entities)


class FritzBoxBatterySensor(FritzBoxEntity, SensorEntity):
    """The entity class for FRITZ!SmartHome sensors."""

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.device.battery_level


class FritzBoxTempSensor(FritzBoxEntity, SensorEntity):
    """The entity class for FRITZ!SmartHome temperature sensors."""

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.device.temperature

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        attrs = {
            ATTR_STATE_DEVICE_LOCKED: self.device.device_lock,
            ATTR_STATE_LOCKED: self.device.lock,
        }
        return attrs
