"""Support for Plugwise Circle(+) nodes."""
from homeassistant.components.switch import SwitchEntity

from . import PlugwiseNodeEntity
from .const import (
    AVAILABLE_SENSOR_ID,
    CURRENT_POWER_SENSOR_ID,
    DOMAIN,
    SENSORS,
    SWITCHES,
    TODAY_ENERGY_SENSOR_ID,
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Plugwise switch based on config_entry."""
    stick = hass.data[DOMAIN][entry.entry_id]["stick"]
    nodes_data = hass.data[DOMAIN][entry.entry_id]["switch"]
    entities = []
    for mac in nodes_data:
        node = stick.node(mac)
        for switch_type in node.get_switches():
            if switch_type in SWITCHES:
                entities.append(PlugwiseSwitch(node, mac, switch_type))
    async_add_entities(entities)


class PlugwiseSwitch(PlugwiseNodeEntity, SwitchEntity):
    """Representation of a switch."""

    def __init__(self, node, mac, switch_id):
        """Initialize a Node entity."""
        super().__init__(node, mac)
        self.switch_id = switch_id
        self.switch_type = SWITCHES[self.switch_id]
        if (CURRENT_POWER_SENSOR_ID in node.get_sensors()) and (
            TODAY_ENERGY_SENSOR_ID in node.get_sensors()
        ):
            self.node_callbacks = (
                AVAILABLE_SENSOR_ID,
                switch_id,
                CURRENT_POWER_SENSOR_ID,
                TODAY_ENERGY_SENSOR_ID,
            )
        else:
            self.node_callbacks = (AVAILABLE_SENSOR_ID, self.switch_id)

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        current_power = getattr(self._node, SENSORS[CURRENT_POWER_SENSOR_ID]["state"])()
        if current_power:
            return float(round(current_power, 2))
        return None

    @property
    def device_class(self):
        """Return the device class of this switch."""
        return self.switch_type["class"]

    @property
    def entity_registry_enabled_default(self):
        """Return the switch registration state."""
        return self.switch_type["enabled_default"]

    @property
    def icon(self):
        """Return the icon."""
        return None if self.switch_type["class"] else self.switch_type["icon"]

    @property
    def is_on(self):
        """Return true if the switch is on."""
        return getattr(self._node, self.switch_type["state"])()

    @property
    def today_energy_kwh(self):
        """Return the today total energy usage in kWh."""
        today_energy = getattr(self._node, SENSORS[TODAY_ENERGY_SENSOR_ID]["state"])()
        if today_energy:
            return float(round(today_energy / 1000, 3))
        return None

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
