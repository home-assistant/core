"""Support for Sure PetCare Flaps/Pets sensors."""
import logging

from surepy import SureThingID

from homeassistant.const import (
    ATTR_VOLTAGE,
    CONF_ID,
    CONF_NAME,
    CONF_TYPE,
    DEVICE_CLASS_BATTERY,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import (
    DATA_SURE_PETCARE,
    SPC,
    SURE_BATT_VOLTAGE_DIFF,
    SURE_BATT_VOLTAGE_LOW,
    TOPIC_UPDATE,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up Sure PetCare Flaps sensors."""
    if discovery_info is None:
        return

    spc = hass.data[DATA_SURE_PETCARE][SPC]
    async_add_entities(
        [
            FlapBattery(entity[CONF_ID], entity[CONF_NAME], spc)
            for entity in spc.ids
            if entity[CONF_TYPE] == SureThingID.FLAP.name
        ],
        True,
    )


class FlapBattery(Entity):
    """Sure Petcare Flap."""

    def __init__(self, _id: int, name: str, spc):
        """Initialize a Sure Petcare Flap battery sensor."""
        self._id = _id
        self._name = f"Flap {name.capitalize()} Battery Level"
        self._spc = spc
        self._state = self._spc.states[SureThingID.FLAP.name][self._id].get("data")

        self._async_unsub_dispatcher_connect = None

    @property
    def should_poll(self):
        """Return true."""
        return False

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
            battery_percent = None

        return battery_percent

    @property
    def unique_id(self):
        """Return an unique ID."""
        return f"{self._spc.household_id}-{self._id}"

    @property
    def device_class(self):
        """Return the device class."""
        return DEVICE_CLASS_BATTERY

    @property
    def device_state_attributes(self):
        """Return state attributes."""
        attributes = None
        if self._state:
            try:
                voltage_per_battery = float(self._state["battery"]) / 4
                attributes = {
                    ATTR_VOLTAGE: f"{float(self._state['battery']):.2f}",
                    f"{ATTR_VOLTAGE}_per_battery": f"{voltage_per_battery:.2f}",
                }
            except (KeyError, TypeError) as error:
                attributes = self._state
                _LOGGER.error(
                    "Error getting device state attributes from %s: %s\n\n%s",
                    self._name,
                    error,
                    self._state,
                )

        return attributes

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "%"

    async def async_update(self):
        """Get the latest data and update the state."""
        self._state = self._spc.states[SureThingID.FLAP.name][self._id].get("data")

    async def async_added_to_hass(self):
        """Register callbacks."""

        @callback
        def update():
            """Update the state."""
            self.async_schedule_update_ha_state(True)

        self._async_unsub_dispatcher_connect = async_dispatcher_connect(
            self.hass, TOPIC_UPDATE, update
        )

    async def async_will_remove_from_hass(self):
        """Disconnect dispatcher listener when removed."""
        if self._async_unsub_dispatcher_connect:
            self._async_unsub_dispatcher_connect()
