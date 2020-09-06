"""The Wolf SmartSet sensors."""
import logging

from wolf_smartset.models import (
    HoursParameter,
    ListItemParameter,
    Parameter,
    PercentageParameter,
    Pressure,
    SimpleParameter,
    Temperature,
)

from homeassistant.components.wolflink.const import (
    COORDINATOR,
    DEVICE_ID,
    DOMAIN,
    PARAMETERS,
    STATES,
)
from homeassistant.const import (
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    PRESSURE_BAR,
    TEMP_CELSIUS,
    TIME_HOURS,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up all entries for Wolf Platform."""

    coordinator = hass.data[DOMAIN][config_entry.entry_id][COORDINATOR]
    parameters = hass.data[DOMAIN][config_entry.entry_id][PARAMETERS]
    device_id = hass.data[DOMAIN][config_entry.entry_id][DEVICE_ID]

    entities = []
    for parameter in parameters:
        if isinstance(parameter, Temperature):
            entities.append(WolfLinkTemperature(coordinator, parameter, device_id))
        if isinstance(parameter, Pressure):
            entities.append(WolfLinkPressure(coordinator, parameter, device_id))
        if isinstance(parameter, PercentageParameter):
            entities.append(WolfLinkPercentage(coordinator, parameter, device_id))
        if isinstance(parameter, ListItemParameter):
            entities.append(WolfLinkState(coordinator, parameter, device_id))
        if isinstance(parameter, HoursParameter):
            entities.append(WolfLinkHours(coordinator, parameter, device_id))
        if isinstance(parameter, SimpleParameter):
            entities.append(WolfLinkSensor(coordinator, parameter, device_id))

    async_add_entities(entities, True)


class WolfLinkSensor(CoordinatorEntity):
    """Base class for all Wolf entities."""

    def __init__(self, coordinator, wolf_object: Parameter, device_id):
        """Initialize."""
        super().__init__(coordinator)
        self.wolf_object = wolf_object
        self.device_id = device_id

    @property
    def name(self):
        """Return the name."""
        return f"{self.wolf_object.name}"

    @property
    def state(self):
        """Return the state."""
        return self.coordinator.data[self.wolf_object.value_id]

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            "parameter_id": self.wolf_object.parameter_id,
            "value_id": self.wolf_object.value_id,
            "parent": self.wolf_object.parent,
        }

    @property
    def unique_id(self):
        """Return a unique_id for this entity."""
        return f"{self.device_id}:{self.wolf_object.parameter_id}"


class WolfLinkHours(WolfLinkSensor):
    """Class for hour based entities."""

    @property
    def icon(self):
        """Icon to display in the front Aend."""
        return "mdi:clock"

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return TIME_HOURS


class WolfLinkTemperature(WolfLinkSensor):
    """Class for temperature based entities."""

    @property
    def device_class(self):
        """Return the device_class."""
        return DEVICE_CLASS_TEMPERATURE

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return TEMP_CELSIUS


class WolfLinkPressure(WolfLinkSensor):
    """Class for pressure based entities."""

    @property
    def device_class(self):
        """Return the device_class."""
        return DEVICE_CLASS_PRESSURE

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return PRESSURE_BAR


class WolfLinkPercentage(WolfLinkSensor):
    """Class for percentage based entities."""

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self.wolf_object.unit


class WolfLinkState(WolfLinkSensor):
    """Class for entities which has defined list of state."""

    @property
    def device_class(self):
        """Return the device class."""
        return "wolflink__state"

    @property
    def state(self):
        """Return the state converting with supported values."""
        state = self.coordinator.data[self.wolf_object.value_id]
        resolved_state = [
            item for item in self.wolf_object.items if item.value == int(state)
        ]
        if resolved_state:
            resolved_name = resolved_state[0].name
            return STATES.get(resolved_name, resolved_name)
        return state
