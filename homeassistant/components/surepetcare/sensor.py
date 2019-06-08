"""Support for Sure PetCare Flaps binary sensors."""
import logging
import pprint

import homeassistant.helpers.device_registry as dr
from homeassistant.const import ATTR_VOLTAGE, CONF_ID, CONF_NAME, CONF_TYPE
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import (BATTERY_DEFAULT_DEVICE_CLASS, BATTERY_DEFAULT_ICON,
                    CONF_HOUSEHOLD_ID, DATA_SURE_PETCARE, DATA_SUREPY,
                    SURE_BATT_VOLTAGE_DIFF, SURE_BATT_VOLTAGE_LOW, SURE_IDS,
                    TOPIC_UPDATE, SureProductID, SureThingID)

_LOGGER = logging.getLogger(__name__)


# async def async_setup_entry(hass, entry, async_add_entities):
async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up Sure PetCare Flaps sensors based on a config entry."""
    from surepy import SurePetcare

    entities = list()
    surepy: SurePetcare = hass.data[DATA_SURE_PETCARE][DATA_SUREPY]

    for thing in hass.data[DATA_SURE_PETCARE][SURE_IDS]:
        sure_id = thing[CONF_ID]
        sure_type = thing[CONF_TYPE]

        if sure_type != SureThingID.FLAP.name:
            continue

        if sure_id not in hass.data[DATA_SURE_PETCARE][sure_type]:
            hass.data[DATA_SURE_PETCARE][
                sure_type][sure_id] = await surepy.get_flap_data(sure_id)

        entities.append(FlapBattery(sure_id, thing[CONF_NAME], hass=hass))

    async_add_entities(entities, True)


class FlapBattery(Entity):
    """Sure Petcare Flap."""

    def __init__(self, _id: int, name: str, data: dict = None, hass=None):
        """Initialize a Sure Petcare Flap battery sensor."""
        self._id = _id
        self._hass = hass
        self._name = f"Flap {name.capitalize()} Battery Level"
        self._unit_of_measurement = "%"
        self._icon = BATTERY_DEFAULT_ICON
        self._device_class = BATTERY_DEFAULT_DEVICE_CLASS

        self._household_id = hass.data[DATA_SURE_PETCARE][CONF_HOUSEHOLD_ID]

        self._state = dict()
        self._data = hass.data[DATA_SURE_PETCARE][SureThingID.FLAP.name]

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def state(self):
        """Return battery level in percent."""
        try:
            per_battery_voltage = self._state["battery"] / 4
            voltage_diff = per_battery_voltage - SURE_BATT_VOLTAGE_LOW
            battery_percent = int(voltage_diff / SURE_BATT_VOLTAGE_DIFF * 100)
        except (KeyError, TypeError):
            battery_percent = False

        return battery_percent

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
        try:
            voltage_per_battery = float(self._state["battery"]) / 4
            attributes = {
                ATTR_VOLTAGE: f"{float(self._state['battery']):.2f} V",
                f"{ATTR_VOLTAGE}_per_battery": f"{voltage_per_battery:.2f} V",
            }
        except (KeyError, TypeError) as error:
            attributes = None
            _LOGGER.debug(
                "error getting device state attributes from %s: %s\n\n%s",
                self._name, error, self._state)

        return attributes

    @property
    def device_info(self):
        """Return information about the device."""
        try:
            device_info = {
                "name": self._name,
                "model": SureProductID.PET_FLAP,
                "manufacturer": 'Sure Petcare',
                "connections": {
                    (dr.CONNECTION_NETWORK_MAC,
                     self._state["mac_address"] or "DEAD1337BEEF1337")
                },
                "sw_version": self._state["version"] or 0,
            }

        except (KeyError, TypeError) as error:
            device_info = None
            _LOGGER.debug(
                "error while getting device info from %s: %s",
                self._name, error)

        return device_info

    async def async_update(self):
        """Get the latest data and update the state."""
        try:
            if self._data[self._id]:
                self._state = self._data[self._id]
            else:
                _LOGGER.debug(
                    "async_update from %s got no new data: %s",
                    self._name, pprint.pformat(self._data))
        except (AttributeError, KeyError, TypeError) as error:
            _LOGGER.debug("async_update error from %s: %s", self._name, error)

    async def async_added_to_hass(self):
        """Register callbacks."""
        @callback
        def update():
            """Update the state."""
            self.async_schedule_update_ha_state(True)

        # pylint: disable=attribute-defined-outside-init
        self._async_unsub_dispatcher_connect = async_dispatcher_connect(
            self._hass, TOPIC_UPDATE, update)

    async def async_will_remove_from_hass(self):
        """Disconnect dispatcher listener when removed."""
        if self._async_unsub_dispatcher_connect:
            self._async_unsub_dispatcher_connect()
