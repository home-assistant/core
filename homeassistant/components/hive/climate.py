"""Support for the Hive climate devices."""
from homeassistant.components.climate import ClimateDevice
from homeassistant.components.climate.const import (
    STATE_AUTO, STATE_HEAT, SUPPORT_AUX_HEAT, SUPPORT_OPERATION_MODE,
    SUPPORT_TARGET_TEMPERATURE)
from homeassistant.const import (
    ATTR_TEMPERATURE, STATE_OFF, STATE_ON, TEMP_CELSIUS)

from . import DATA_HIVE, DOMAIN

DEPENDENCIES = ['hive']

HIVE_TO_HASS_STATE = {
    'SCHEDULE': STATE_AUTO,
    'MANUAL': STATE_HEAT,
    'ON': STATE_ON,
    'OFF': STATE_OFF,
}

HASS_TO_HIVE_STATE = {
    STATE_AUTO: 'SCHEDULE',
    STATE_HEAT: 'MANUAL',
    STATE_ON: 'ON',
    STATE_OFF: 'OFF',
}

SUPPORT_FLAGS = (SUPPORT_TARGET_TEMPERATURE |
                 SUPPORT_OPERATION_MODE |
                 SUPPORT_AUX_HEAT)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up Hive climate devices."""
    if discovery_info is None:
        return
    session = hass.data.get(DATA_HIVE)

    add_entities([HiveClimateEntity(session, discovery_info)])


class HiveClimateEntity(ClimateDevice):
    """Hive Climate Device."""

    def __init__(self, hivesession, hivedevice):
        """Initialize the Climate device."""
        self.node_id = hivedevice["Hive_NodeID"]
        self.node_name = hivedevice["Hive_NodeName"]
        self.device_type = hivedevice["HA_DeviceType"]
        if self.device_type == "Heating":
            self.thermostat_node_id = hivedevice["Thermostat_NodeID"]
        self.session = hivesession
        self.attributes = {}
        self.data_updatesource = '{}.{}'.format(
            self.device_type, self.node_id)
        self._unique_id = '{}-{}'.format(self.node_id, self.device_type)

        if self.device_type == "Heating":
            self.modes = [STATE_AUTO, STATE_HEAT, STATE_OFF]
        elif self.device_type == "HotWater":
            self.modes = [STATE_AUTO, STATE_ON, STATE_OFF]

        self.session.entities.append(self)

    @property
    def unique_id(self):
        """Return unique ID of entity."""
        return self._unique_id

    @property
    def device_info(self):
        """Return device information."""
        return {
            'identifiers': {
                (DOMAIN, self.unique_id)
            },
            'name': self.name
        }

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    def handle_update(self, updatesource):
        """Handle the new update request."""
        if '{}.{}'.format(self.device_type, self.node_id) not in updatesource:
            self.schedule_update_ha_state()

    @property
    def name(self):
        """Return the name of the Climate device."""
        friendly_name = "Climate Device"
        if self.device_type == "Heating":
            friendly_name = "Heating"
            if self.node_name is not None:
                friendly_name = '{} {}'.format(self.node_name, friendly_name)
        elif self.device_type == "HotWater":
            friendly_name = "Hot Water"
        return friendly_name

    @property
    def device_state_attributes(self):
        """Show Device Attributes."""
        return self.attributes

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        if self.device_type == "Heating":
            return self.session.heating.current_temperature(self.node_id)

    @property
    def target_temperature(self):
        """Return the target temperature."""
        if self.device_type == "Heating":
            return self.session.heating.get_target_temperature(self.node_id)

    @property
    def min_temp(self):
        """Return minimum temperature."""
        if self.device_type == "Heating":
            return self.session.heating.min_temperature(self.node_id)

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        if self.device_type == "Heating":
            return self.session.heating.max_temperature(self.node_id)

    @property
    def operation_list(self):
        """List of the operation modes."""
        return self.modes

    @property
    def current_operation(self):
        """Return current mode."""
        if self.device_type == "Heating":
            currentmode = self.session.heating.get_mode(self.node_id)
        elif self.device_type == "HotWater":
            currentmode = self.session.hotwater.get_mode(self.node_id)
        return HIVE_TO_HASS_STATE.get(currentmode)

    def set_operation_mode(self, operation_mode):
        """Set new Heating mode."""
        new_mode = HASS_TO_HIVE_STATE.get(operation_mode)
        if self.device_type == "Heating":
            self.session.heating.set_mode(self.node_id, new_mode)
        elif self.device_type == "HotWater":
            self.session.hotwater.set_mode(self.node_id, new_mode)

        for entity in self.session.entities:
            entity.handle_update(self.data_updatesource)

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        new_temperature = kwargs.get(ATTR_TEMPERATURE)
        if new_temperature is not None:
            if self.device_type == "Heating":
                self.session.heating.set_target_temperature(self.node_id,
                                                            new_temperature)

            for entity in self.session.entities:
                entity.handle_update(self.data_updatesource)

    @property
    def is_aux_heat_on(self):
        """Return true if auxiliary heater is on."""
        boost_status = None
        if self.device_type == "Heating":
            boost_status = self.session.heating.get_boost(self.node_id)
        elif self.device_type == "HotWater":
            boost_status = self.session.hotwater.get_boost(self.node_id)
        return boost_status == "ON"

    def turn_aux_heat_on(self):
        """Turn auxiliary heater on."""
        target_boost_time = 30
        if self.device_type == "Heating":
            curtemp = self.session.heating.current_temperature(self.node_id)
            curtemp = round(curtemp * 2) / 2
            target_boost_temperature = curtemp + 0.5
            self.session.heating.turn_boost_on(self.node_id,
                                               target_boost_time,
                                               target_boost_temperature)
        elif self.device_type == "HotWater":
            self.session.hotwater.turn_boost_on(self.node_id,
                                                target_boost_time)

        for entity in self.session.entities:
            entity.handle_update(self.data_updatesource)

    def turn_aux_heat_off(self):
        """Turn auxiliary heater off."""
        if self.device_type == "Heating":
            self.session.heating.turn_boost_off(self.node_id)
        elif self.device_type == "HotWater":
            self.session.hotwater.turn_boost_off(self.node_id)

        for entity in self.session.entities:
            entity.handle_update(self.data_updatesource)

    def update(self):
        """Update all Node data from Hive."""
        node = self.node_id
        if self.device_type == "Heating":
            node = self.thermostat_node_id

        self.session.core.update_data(self.node_id)
        self.attributes = self.session.attributes.state_attributes(node)
