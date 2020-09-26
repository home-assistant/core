"""Support for the Hive switches."""
from homeassistant.components.switch import SwitchEntity

from . import DATA_HIVE, DOMAIN, HiveEntity, refresh_system


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up Hive switches."""
    if discovery_info is None:
        return

    session = hass.data.get(DATA_HIVE)
    devs = []
    for dev in discovery_info:
        devs.append(HiveDevicePlug(session, dev))
    add_entities(devs)


class HiveDevicePlug(HiveEntity, SwitchEntity):
    """Hive Active Plug."""

    @property
    def unique_id(self):
        """Return unique ID of entity."""
        return self._unique_id

    @property
    def device_info(self):
        """Return device information."""
        return {"identifiers": {(DOMAIN, self.unique_id)}, "name": self.name}

    @property
    def name(self):
        """Return the name of this Switch device if any."""
        return self.node_name

    @property
    def device_state_attributes(self):
        """Show Device Attributes."""
        return self.attributes

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        return self.session.switch.get_power_usage(self.node_id)

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.session.switch.get_state(self.node_id)

    @refresh_system
    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self.session.switch.turn_on(self.node_id)

    @refresh_system
    def turn_off(self, **kwargs):
        """Turn the device off."""
        self.session.switch.turn_off(self.node_id)

    def update(self):
        """Update all Node data from Hive."""
        self.session.core.update_data(self.node_id)
        self.attributes = self.session.attributes.state_attributes(self.node_id)
