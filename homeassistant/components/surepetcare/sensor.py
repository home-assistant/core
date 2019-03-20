"""Support for Sure PetCare Flaps binary sensors."""
import logging

import homeassistant.helpers.device_registry as dr
from homeassistant.const import ATTR_VOLTAGE, CONF_ID, CONF_NAME, CONF_TYPE
from homeassistant.helpers.entity import Entity

from .const import (BATTERY_DEFAULT_DEVICE_CLASS, BATTERY_DEFAULT_ICON,
                    CONF_HOUSEHOLD_ID, DATA_SURE_PETCARE,
                    SURE_BATTERY_VOLTAGE_DIFF, SURE_BATTERY_VOLTAGE_LOW,
                    SURE_IDS, SureProductID, SureThingType)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Sure PetCare Flaps sensors based on a config entry."""
    hass.data[DATA_SURE_PETCARE][CONF_HOUSEHOLD_ID] = entry.data[
        CONF_HOUSEHOLD_ID]
    hass.data[DATA_SURE_PETCARE][SureThingType.FLAP.name] = dict()

    entities = list()

    for thing in hass.data[DATA_SURE_PETCARE][SURE_IDS]:
        sure_id = thing[CONF_ID]
        sure_type = thing[CONF_TYPE]

        if sure_type != SureThingType.FLAP.name:
            continue

        if sure_id not in hass.data[DATA_SURE_PETCARE][sure_type]:
            hass.data[DATA_SURE_PETCARE][sure_type][sure_id] = None

        entities.append(FlapBattery(sure_id, thing[CONF_NAME], hass))

    async_add_entities(entities)


class FlapBattery(Entity):
    """Sure Petcare Flap."""

    def __init__(self, _id: int, name: int, hass=None):
        self._icon = BATTERY_DEFAULT_ICON
        self._device_class = BATTERY_DEFAULT_DEVICE_CLASS
        self._id = _id
        self._name = f"Flap {name.capitalize()} Battery Level"
        self._hass = hass
        self._household_id = hass.data[DATA_SURE_PETCARE][CONF_HOUSEHOLD_ID]
        self._state = dict()
        self._data = hass.data[DATA_SURE_PETCARE][SureThingType.FLAP.name]
        self._unit_of_measurement = "%"

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def state(self):
        """Return battery level in percent."""
        try:
            per_battery_voltage = self._state["battery"] / 4
            voltage_diff_to_low = per_battery_voltage - SURE_BATTERY_VOLTAGE_LOW

            return int(voltage_diff_to_low / SURE_BATTERY_VOLTAGE_DIFF * 100)
        except (KeyError, TypeError):
            return False

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def unique_id(self):
        """Return an unique ID."""
        return "{}-{}-battery-level".format(self._household_id, self._id)

    @property
    def device_state_attributes(self):
        """Return an unique ID."""
        attributes = None
        if self._state:
            voltage_per_battery = float(self._state["battery"]) / 4
            attributes = {
                ATTR_VOLTAGE: f"{float(self._state['battery']):.2f} V",
                f"{ATTR_VOLTAGE}_per_battery": f"{voltage_per_battery:.2f} V",
            }

        return attributes

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            "name": self._name,
            "model": SureProductID.PET_FLAP,
            "manufacturer": 'Sure Petcare',
            "connections": {
                (dr.CONNECTION_NETWORK_MAC, "38B953FEFF3980D8")
            },
            "sw_version": 0,
        }

    async def async_update(self):
        """Get the latest data and update the state."""
        try:
            self._state = self._data[self._id]
        except (AttributeError, KeyError, TypeError):
            pass
