"""
Support for the Hive devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/hive/
"""
import logging
from datetime import datetime

from homeassistant.components.climate import (ENTITY_ID_FORMAT, ClimateDevice,
                                              STATE_AUTO, STATE_HEAT,
                                              STATE_OFF, STATE_ON)
from homeassistant.const import ATTR_TEMPERATURE, TEMP_CELSIUS
from homeassistant.components.hive import DATA_HIVE

DEPENDENCIES = ['hive']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, hivedevice, discovery_info=None):
    """Set up Hive climate devices."""
    session = hass.data.get(DATA_HIVE)

    add_devices([HiveClimateEntity(hass, session, hivedevice)])


class HiveClimateEntity(ClimateDevice):
    """Hive Climate Device."""

    def __init__(self, hass, Session, HiveDevice):
        """Initialize the Climate device."""
        self.node_id = HiveDevice["Hive_NodeID"]
        self.node_name = HiveDevice["Hive_NodeName"]
        self.device_type = HiveDevice["HA_DeviceType"]
        self.hass = hass
        self.session = Session

        if self.device_type == "Heating":
            set_entity_id = "Hive_Heating"
            self.session.heating = self.session.core.Heating()
            self.modes = [STATE_AUTO, STATE_HEAT, STATE_OFF]
        elif self.device_type == "HotWater":
            set_entity_id = "Hive_HotWater"
            self.session.hotwater = self.session.core.Hotwater()
            self.modes = [STATE_AUTO, STATE_ON, STATE_OFF]
        if self.node_name is not None:
            set_entity_id = set_entity_id + "_" \
                            + self.node_name.replace(" ", "_")
        self.entity_id = ENTITY_ID_FORMAT.format(set_entity_id.lower())

        self.session.entities.append(self)

    def handle_update(self, updatesource):
        """Handle the new update request."""
        if self.device_type + "." + self.node_id not in updatesource:
            self.schedule_update_ha_state()

    @property
    def name(self):
        """Return the name of the Climate device."""
        friendly_name = "Climate Device"
        if self.device_type == "Heating":
            friendly_name = "Heating"
            if self.node_name is not None:
                friendly_name = self.node_name + " " + friendly_name

        elif self.device_type == "HotWater":
            friendly_name = "Hot Water"

        return friendly_name

    @property
    def force_update(self):
        """Return True if state updates should be forced."""
        return False

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement which this device uses."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        if self.device_type == "Heating":
            nodeid = self.node_id
            curtempret = self.session.heating.current_temperature(nodeid)

            if curtempret != -1000:
                if nodeid in self.session.data.minmax:
                    if (self.session.data.minmax[nodeid]['TodayDate'] !=
                            datetime.date(datetime.now())):
                        self.session.data.minmax[nodeid]['TodayMin'] = 1000
                        self.session.data.minmax[nodeid]['TodayMax'] = -1000
                        self.session.data.minmax[nodeid]['TodayDate'] = \
                            datetime.date(datetime.now())

                    if (curtempret < self.session.data.minmax[nodeid]
                            ['TodayMin']):
                        self.session.data.minmax[nodeid]['TodayMin'] = \
                            curtempret

                    if (curtempret > self.session.data.minmax[nodeid]
                            ['TodayMax']):
                        self.session.data.minmax[nodeid]['TodayMax'] = \
                            curtempret

                    if (curtempret < self.session.data.minmax[nodeid]
                            ['RestartMin']):
                        self.session.data.minmax[nodeid]['RestartMin'] = \
                            curtempret

                    if (curtempret >
                            self.session.data.minmax[nodeid]
                            ['RestartMax']):
                        self.session.data.minmax[nodeid]['RestartMax'] = \
                            curtempret
                else:
                    current_node_max_min_data = {}
                    current_node_max_min_data['TodayMin'] = curtempret
                    current_node_max_min_data['TodayMax'] = curtempret
                    current_node_max_min_data['TodayDate'] = \
                        datetime.date(datetime.now())
                    current_node_max_min_data['RestartMin'] = curtempret
                    current_node_max_min_data['RestartMax'] = curtempret
                    self.session.data.minmax[nodeid] = \
                        current_node_max_min_data
            else:
                curtempret = 0
            return curtempret
        elif self.device_type == "HotWater":
            return None

    @property
    def target_temperature(self):
        """Return the target temperature."""
        set_result = None

        if self.device_type == "Heating":
            set_result = self.session.heating.get_target_temperature(
                self.node_id)
        elif self.device_type == "HotWater":
            set_result = None

        return set_result

    @property
    def min_temp(self):
        """Return minimum temperature."""
        if self.device_type == "Heating":
            return self.session.heating.min_temperature(self.node_id)
        elif self.device_type == "HotWater":
            return None

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        if self.device_type == "Heating":
            return self.session.heating.max_temperature(self.node_id)
        elif self.device_type == "HotWater":
            return None

    @property
    def operation_list(self):
        """List of the operation modes."""
        return self.modes

    @property
    def current_operation(self):
        """Return current mode."""
        if self.device_type == "Heating":
            currentmode = self.session.heating.get_mode(self.node_id)
            if currentmode == "SCHEDULE":
                return STATE_AUTO
            elif currentmode == "MANUAL":
                return STATE_HEAT
            elif currentmode == "OFF":
                return STATE_OFF
        elif self.device_type == "HotWater":
            currentmode = self.session.hotwater.get_mode(self.node_id)
            if currentmode == "SCHEDULE":
                return STATE_AUTO
            elif currentmode == "ON":
                return STATE_ON
            elif currentmode == "OFF":
                return STATE_OFF

    def set_operation_mode(self, operation_mode):
        """Set new Heating mode."""
        if self.device_type == "Heating":
            if operation_mode == STATE_AUTO:
                new_mode = "SCHEDULE"
            elif operation_mode == STATE_HEAT:
                new_mode = "MANUAL"
            elif operation_mode == STATE_OFF:
                new_mode = "OFF"
            self.session.heating.set_mode(self.node_id, new_mode)
        elif self.device_type == "HotWater":
            if operation_mode == STATE_AUTO:
                new_mode = "SCHEDULE"
            elif operation_mode == STATE_ON:
                new_mode = "ON"
            elif operation_mode == STATE_OFF:
                new_mode = "OFF"
            self.session.hotwater.set_mode(self.node_id, new_mode)

        updatesource = self.device_type + "." + self.node_id
        for entity in self.session.entities:
            entity.handle_update(updatesource)

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        if kwargs.get(ATTR_TEMPERATURE) is not None:
            new_temperature = kwargs.get(ATTR_TEMPERATURE)
            if self.device_type == "Heating":
                self.session.heating.set_target_temperature(self.node_id,
                                                            new_temperature)
            updatesource = self.device_type + "." + self.node_id
            for entity in self.session.entities:
                entity.handle_update(updatesource)

    def update(self):
        """Update all Node data frome Hive."""
        self.session.core.hive_api_get_nodes_rl(self.node_id)
