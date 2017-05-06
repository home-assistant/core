"""
Support for MySensors switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.mysensors/
"""
import logging
import os

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components import mysensors
from homeassistant.components.switch import DOMAIN, SwitchDevice
from homeassistant.config import load_yaml_config_file
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = []

ATTR_IR_CODE = 'V_IR_SEND'
SERVICE_SEND_IR_CODE = 'mysensors_send_ir_code'

SEND_IR_CODE_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_IR_CODE): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the mysensors platform for switches."""
    # Only act if loaded via mysensors by discovery event.
    # Otherwise gateway is not setup.
    if discovery_info is None:
        return

    gateways = hass.data.get(mysensors.MYSENSORS_GATEWAYS)
    if not gateways:
        return

    platform_devices = []

    for gateway in gateways:
        # Define the S_TYPES and V_TYPES that the platform should handle as
        # states. Map them in a dict of lists.
        pres = gateway.const.Presentation
        set_req = gateway.const.SetReq
        map_sv_types = {
            pres.S_DOOR: [set_req.V_ARMED],
            pres.S_MOTION: [set_req.V_ARMED],
            pres.S_SMOKE: [set_req.V_ARMED],
            pres.S_LIGHT: [set_req.V_LIGHT],
            pres.S_LOCK: [set_req.V_LOCK_STATUS],
            pres.S_IR: [set_req.V_IR_SEND],
        }
        device_class_map = {
            pres.S_DOOR: MySensorsSwitch,
            pres.S_MOTION: MySensorsSwitch,
            pres.S_SMOKE: MySensorsSwitch,
            pres.S_LIGHT: MySensorsSwitch,
            pres.S_LOCK: MySensorsSwitch,
            pres.S_IR: MySensorsIRSwitch,
        }
        if float(gateway.protocol_version) >= 1.5:
            map_sv_types.update({
                pres.S_BINARY: [set_req.V_STATUS, set_req.V_LIGHT],
                pres.S_SPRINKLER: [set_req.V_STATUS],
                pres.S_WATER_LEAK: [set_req.V_ARMED],
                pres.S_SOUND: [set_req.V_ARMED],
                pres.S_VIBRATION: [set_req.V_ARMED],
                pres.S_MOISTURE: [set_req.V_ARMED],
            })
            map_sv_types[pres.S_LIGHT].append(set_req.V_STATUS)
            device_class_map.update({
                pres.S_BINARY: MySensorsSwitch,
                pres.S_SPRINKLER: MySensorsSwitch,
                pres.S_WATER_LEAK: MySensorsSwitch,
                pres.S_SOUND: MySensorsSwitch,
                pres.S_VIBRATION: MySensorsSwitch,
                pres.S_MOISTURE: MySensorsSwitch,
            })
        if float(gateway.protocol_version) >= 2.0:
            map_sv_types.update({
                pres.S_WATER_QUALITY: [set_req.V_STATUS],
            })
            device_class_map.update({
                pres.S_WATER_QUALITY: MySensorsSwitch,
            })

        devices = {}
        gateway.platform_callbacks.append(mysensors.pf_callback_factory(
            map_sv_types, devices, device_class_map, add_devices))
        platform_devices.append(devices)

    def send_ir_code_service(service):
        """Set IR code as device state attribute."""
        entity_ids = service.data.get(ATTR_ENTITY_ID)
        ir_code = service.data.get(ATTR_IR_CODE)

        if entity_ids:
            _devices = [device for gw_devs in platform_devices
                        for device in gw_devs.values()
                        if isinstance(device, MySensorsIRSwitch) and
                        device.entity_id in entity_ids]
        else:
            _devices = [device for gw_devs in platform_devices
                        for device in gw_devs.values()
                        if isinstance(device, MySensorsIRSwitch)]

        kwargs = {ATTR_IR_CODE: ir_code}
        for device in _devices:
            device.turn_on(**kwargs)

    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    hass.services.register(DOMAIN, SERVICE_SEND_IR_CODE,
                           send_ir_code_service,
                           descriptions.get(SERVICE_SEND_IR_CODE),
                           schema=SEND_IR_CODE_SERVICE_SCHEMA)


class MySensorsSwitch(mysensors.MySensorsDeviceEntity, SwitchDevice):
    """Representation of the value of a MySensors Switch child node."""

    @property
    def assumed_state(self):
        """Return True if unable to access real state of entity."""
        return self.gateway.optimistic

    @property
    def is_on(self):
        """Return True if switch is on."""
        if self.value_type in self._values:
            return self._values[self.value_type] == STATE_ON
        return False

    def turn_on(self):
        """Turn the switch on."""
        self.gateway.set_child_value(
            self.node_id, self.child_id, self.value_type, 1)
        if self.gateway.optimistic:
            # optimistically assume that switch has changed state
            self._values[self.value_type] = STATE_ON
            self.schedule_update_ha_state()

    def turn_off(self):
        """Turn the switch off."""
        self.gateway.set_child_value(
            self.node_id, self.child_id, self.value_type, 0)
        if self.gateway.optimistic:
            # optimistically assume that switch has changed state
            self._values[self.value_type] = STATE_OFF
            self.schedule_update_ha_state()


class MySensorsIRSwitch(MySensorsSwitch):
    """IR switch child class to MySensorsSwitch."""

    def __init__(self, *args):
        """Set up instance attributes."""
        MySensorsSwitch.__init__(self, *args)
        self._ir_code = None

    @property
    def is_on(self):
        """Return True if switch is on."""
        set_req = self.gateway.const.SetReq
        if set_req.V_LIGHT in self._values:
            return self._values[set_req.V_LIGHT] == STATE_ON
        return False

    def turn_on(self, **kwargs):
        """Turn the IR switch on."""
        set_req = self.gateway.const.SetReq
        if set_req.V_LIGHT not in self._values:
            _LOGGER.error('missing value_type: %s at node: %s, child: %s',
                          set_req.V_LIGHT.name, self.node_id, self.child_id)
            return
        if ATTR_IR_CODE in kwargs:
            self._ir_code = kwargs[ATTR_IR_CODE]
        self.gateway.set_child_value(
            self.node_id, self.child_id, self.value_type, self._ir_code)
        self.gateway.set_child_value(
            self.node_id, self.child_id, set_req.V_LIGHT, 1)
        if self.gateway.optimistic:
            # optimistically assume that switch has changed state
            self._values[self.value_type] = self._ir_code
            self._values[set_req.V_LIGHT] = STATE_ON
            self.schedule_update_ha_state()
            # turn off switch after switch was turned on
            self.turn_off()

    def turn_off(self):
        """Turn the IR switch off."""
        set_req = self.gateway.const.SetReq
        if set_req.V_LIGHT not in self._values:
            _LOGGER.error('missing value_type: %s at node: %s, child: %s',
                          set_req.V_LIGHT.name, self.node_id, self.child_id)
            return
        self.gateway.set_child_value(
            self.node_id, self.child_id, set_req.V_LIGHT, 0)
        if self.gateway.optimistic:
            # optimistically assume that switch has changed state
            self._values[set_req.V_LIGHT] = STATE_OFF
            self.schedule_update_ha_state()

    def update(self):
        """Update the controller with the latest value from a sensor."""
        MySensorsSwitch.update(self)
        if self.value_type in self._values:
            self._ir_code = self._values[self.value_type]
