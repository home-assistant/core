"""Support for Sure PetCare Flaps/Pets sensors."""
import logging
from typing import Any, Dict, Optional

from surepy import SureLockStateID, SureProductID

from homeassistant.const import (
    ATTR_VOLTAGE,
    CONF_ID,
    CONF_TYPE,
    DEVICE_CLASS_BATTERY,
    PERCENTAGE,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from . import SurePetcareAPI
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

    entities = []

    spc = hass.data[DATA_SURE_PETCARE][SPC]

    for entity in spc.ids:
        sure_type = entity[CONF_TYPE]

        if sure_type in [
            SureProductID.CAT_FLAP,
            SureProductID.PET_FLAP,
            SureProductID.FEEDER,
        ]:
            entities.append(SureBattery(entity[CONF_ID], sure_type, spc))

        if sure_type in [SureProductID.CAT_FLAP, SureProductID.PET_FLAP]:
            entities.append(Flap(entity[CONF_ID], sure_type, spc))

    async_add_entities(entities, True)


class SurePetcareSensor(Entity):
    """A binary sensor implementation for Sure Petcare Entities."""

    def __init__(self, _id: int, sure_type: SureProductID, spc: SurePetcareAPI):
        """Initialize a Sure Petcare sensor."""

        self._id = _id
        self._sure_type = sure_type

        self._spc = spc
        self._spc_data: Dict[str, Any] = self._spc.states[self._sure_type].get(self._id)
        self._state: Dict[str, Any] = {}

        self._name = (
            f"{self._sure_type.name.capitalize()} "
            f"{self._spc_data['name'].capitalize()}"
        )

        self._async_unsub_dispatcher_connect = None

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return an unique ID."""
        return f"{self._spc_data['household_id']}-{self._id}"

    @property
    def available(self) -> bool:
        """Return true if entity is available."""
        return bool(self._state)

    @property
    def should_poll(self) -> bool:
        """Return true."""
        return False

    async def async_update(self) -> None:
        """Get the latest data and update the state."""
        self._spc_data = self._spc.states[self._sure_type].get(self._id)
        self._state = self._spc_data.get("status")
        _LOGGER.debug("%s -> self._state: %s", self._name, self._state)

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        @callback
        def update() -> None:
            """Update the state."""
            self.async_schedule_update_ha_state(True)

        self._async_unsub_dispatcher_connect = async_dispatcher_connect(
            self.hass, TOPIC_UPDATE, update
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect dispatcher listener when removed."""
        if self._async_unsub_dispatcher_connect:
            self._async_unsub_dispatcher_connect()


class Flap(SurePetcareSensor):
    """Sure Petcare Flap."""

    @property
    def state(self) -> Optional[int]:
        """Return battery level in percent."""
        return SureLockStateID(self._state["locking"]["mode"]).name.capitalize()

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the state attributes of the device."""
        attributes = None
        if self._state:
            attributes = {"learn_mode": bool(self._state["learn_mode"])}

        return attributes


class SureBattery(SurePetcareSensor):
    """Sure Petcare Flap."""

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        return f"{self._name} Battery Level"

    @property
    def state(self) -> Optional[int]:
        """Return battery level in percent."""
        battery_percent: Optional[int]
        try:
            per_battery_voltage = self._state["battery"] / 4
            voltage_diff = per_battery_voltage - SURE_BATT_VOLTAGE_LOW
            battery_percent = min(int(voltage_diff / SURE_BATT_VOLTAGE_DIFF * 100), 100)
        except (KeyError, TypeError):
            battery_percent = None

        return battery_percent

    @property
    def unique_id(self) -> str:
        """Return an unique ID."""
        return f"{self._spc_data['household_id']}-{self._id}-battery"

    @property
    def device_class(self) -> str:
        """Return the device class."""
        return DEVICE_CLASS_BATTERY

    @property
    def device_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return state attributes."""
        attributes = None
        if self._state:
            voltage_per_battery = float(self._state["battery"]) / 4
            attributes = {
                ATTR_VOLTAGE: f"{float(self._state['battery']):.2f}",
                f"{ATTR_VOLTAGE}_per_battery": f"{voltage_per_battery:.2f}",
            }

        return attributes

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return PERCENTAGE
