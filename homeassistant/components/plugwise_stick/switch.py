"""Support for Plugwise Circle(+) nodes."""
import logging

from homeassistant.components.switch import SwitchDevice

from . import PlugwiseNodeEntity
from .const import (
    AVAILABLE_SENSOR_ID,
    CURRENT_POWER_SENSOR_ID,
    DOMAIN,
    SENSORS,
    SWITCHES,
    TODAY_ENERGY_SENSOR_ID,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Plugwise switch based on config_entry."""
    stick = hass.data[DOMAIN][entry.entry_id]["stick"]
    nodes_data = hass.data[DOMAIN][entry.entry_id]["switch"]
    entities = []
    for mac in nodes_data:
        node = stick.node(mac)
        for switch_type in node.get_switches():
            if switch_type in SWITCHES:
                if (CURRENT_POWER_SENSOR_ID in node.get_sensors()) and (
                    TODAY_ENERGY_SENSOR_ID in node.get_sensors()
                ):
                    entities.append(
                        PlugwiseSwitchWithPower(
                            node,
                            mac,
                            switch_type,
                            CURRENT_POWER_SENSOR_ID,
                            TODAY_ENERGY_SENSOR_ID,
                        )
                    )
                else:
                    entities.append(PlugwiseSwitch(node, mac, switch_type))
    async_add_entities(entities)


class PlugwiseSwitch(PlugwiseNodeEntity, SwitchDevice):
    """Representation of a switch."""

    def __init__(self, node, mac, switch_id):
        """Initialize a Node entity."""
        super().__init__(node, mac)
        self.switch_id = switch_id
        self.switch_type = SWITCHES[self.switch_id]
        self.node_callbacks = (AVAILABLE_SENSOR_ID, self.switch_id)

    @property
    def entity_registry_enabled_default(self):
        """Default sensor registration."""
        return self.switch_type["enabled_default"]

    @property
    def icon(self):
        """Return the icon."""
        return self.switch_type["icon"]

    @property
    def is_on(self):
        """Return true if the switch is on."""
        return getattr(self._node, self.switch_type["state"])()

    def turn_off(self, **kwargs):
        """Instruct the switch to turn off."""
        getattr(self._node, self.switch_type["switch"])(False)

    def turn_on(self, **kwargs):
        """Instruct the switch to turn on."""
        getattr(self._node, self.switch_type["switch"])(True)

    @property
    def unique_id(self):
        """Get unique ID."""
        return f"{self._mac}-{self.switch_id}"


class PlugwiseSwitchWithPower(PlugwiseSwitch, SwitchDevice):
    """Representation of a switch with power measurement."""

    def __init__(self, node, mac, switch_id, power_sensor_id, energy_sensor_id):
        """Initialize a Node entity."""
        super().__init__(node, mac, switch_id)
        self.power_sensor = SENSORS[power_sensor_id]
        self.energy_sensor = SENSORS[energy_sensor_id]
        self.sensor_callbacks = (
            AVAILABLE_SENSOR_ID,
            switch_id,
            power_sensor_id,
            energy_sensor_id,
        )

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        if getattr(self._node, self.power_sensor["state"])():
            return float(round(getattr(self._node, self.power_sensor["state"])(), 2))
        return None

    @property
    def today_energy_kwh(self):
        """Return the today total energy usage in kWh."""
        if getattr(self._node, self.energy_sensor["state"])():
            return float(round(getattr(self._node, self.energy_sensor["state"])() / 1000, 3))
        return None

    @property
    def unique_id(self):
        """Get unique ID."""
        return f"{self._mac}-{self.switch_id}"
