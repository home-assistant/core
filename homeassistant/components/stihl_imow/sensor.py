"""Platform for sensor integration."""
import logging

from imow.common.mowerstate import MowerState

from homeassistant import config_entries, core
from homeassistant.components.sensor import SensorEntity

from . import extract_properties_by_type
from ...const import STATE_OFF
from .const import DOMAIN
from .entity import ImowBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities,
):
    """Add sensors for passed config_entry in HA."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]

    mower_state: MowerState = config["coordinator"].data

    entities, device = extract_properties_by_type(
        mower_state, bool, negotiate=True  # all, but bool
    )

    async_add_entities(
        ImowSensorEntity(coordinator, device, idx, mower_state_property)
        for idx, mower_state_property in enumerate(entities)
    )


class ImowSensorEntity(ImowBaseEntity, SensorEntity):
    """Representation of a Sensor."""

    def __init__(self, coordinator, device_info, idx, mower_state_property):
        """Override the BaseEntity with Binary Sensor content."""
        super().__init__(coordinator, device_info, idx, mower_state_property)

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        if self.property_name == "machineState":
            return {
                "short": self.mowerstate.stateMessage["short"],
                "long": self.mowerstate.stateMessage["long"],
            }

    @property
    def state(self):
        """Return the state of the sensor."""
        return (
            self.get_value_from_mowerstate()
            if bool(self.get_value_from_mowerstate())
            else STATE_OFF
        )
