"""
HDMI CEC component.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/hdmi_cec/
"""
import logging
import os
from collections import defaultdict
from functools import reduce

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components import discovery
from homeassistant.config import load_yaml_config_file
from homeassistant.const import (EVENT_HOMEASSISTANT_START, STATE_UNKNOWN,
                                 EVENT_HOMEASSISTANT_STOP, STATE_ON,
                                 STATE_OFF, CONF_DEVICES)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['pyCEC>=0.3.4']

DOMAIN = 'hdmi_cec'

_LOGGER = logging.getLogger(__name__)

ICON_UNKNOWN = 'mdi:help'
ICON_AUDIO = 'mdi:speaker'
ICON_PLAYER = 'mdi:play'
ICON_TUNER = 'mdi:nest-thermostat'
ICON_RECORDER = 'mdi:microphone'
ICON_TV = 'mdi:television'
ICONS_BY_TYPE = {
    0: ICON_TV,
    1: ICON_RECORDER,
    3: ICON_TUNER,
    4: ICON_PLAYER,
    5: ICON_AUDIO
}

CEC_DEVICES = defaultdict(list)

CMD_UP = 'up'
CMD_DOWN = 'down'
CMD_MUTE = 'mute'
CMD_UNMUTE = 'unmute'
CMD_MUTE_TOGGLE = 'toggle mute'

EVENT_CEC_COMMAND_RECEIVED = 'cec_command_received'
EVENT_CEC_KEYPRESS_RECEIVED = 'cec_keypress_received'

ATTR_PHYSICAL_ADDRESS = 'physical_address'
ATTR_TYPE_ID = 'type_id'
ATTR_VENDOR_NAME = 'vendor_name'
ATTR_VENDOR_ID = 'vendor_id'
ATTR_DEVICE = 'device'
ATTR_COMMAND = 'command'
ATTR_TYPE = 'type'
ATTR_KEY = 'key'
ATTR_DUR = 'dur'
ATTR_SRC = 'src'
ATTR_DST = 'dst'
ATTR_CMD = 'cmd'
ATTR_ATT = 'att'
ATTR_RAW = 'raw'
ATTR_DIR = 'dir'
ATTR_ABT = 'abt'
ATTR_NEW = 'new'

SERVICE_SEND_COMMAND = 'send_command'
SERVICE_SEND_COMMAND_SCHEMA = vol.Schema({
    vol.Optional(ATTR_CMD): vol.Coerce(int),
    vol.Optional(ATTR_SRC): vol.Coerce(int),
    vol.Optional(ATTR_DST): vol.Coerce(int),
    vol.Optional(ATTR_ATT): vol.Coerce(int),
    vol.Optional(ATTR_RAW): vol.Coerce(str)
}, extra=vol.ALLOW_EXTRA)

SERVICE_VOLUME = 'volume'
SERVICE_VOLUME_SCHEMA = vol.Schema({
    vol.Optional(CMD_UP): vol.Coerce(int),
    vol.Optional(CMD_DOWN): vol.Coerce(int),
    vol.Optional(CMD_MUTE): None,
    vol.Optional(CMD_UNMUTE): None,
    vol.Optional(CMD_MUTE_TOGGLE): None
}, extra=vol.ALLOW_EXTRA)

SERVICE_UPDATE_DEVICES = 'update'
SERVICE_UPDATE_DEVICES_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({})
}, extra=vol.ALLOW_EXTRA)

SERVICE_SELECT_DEVICE = 'select_device'
# pylint: disable=unnecessary-lambda
DEVICE_SCHEMA = vol.Schema({
    vol.All(cv.positive_int): vol.Any(lambda devices: DEVICE_SCHEMA(devices),
                                      cv.string)
})

SERVICE_POWER_ON = 'power_on'
SERVICE_STANDBY = 'standby'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_DEVICES): vol.Schema({cv.string: cv.string})
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass: HomeAssistant, base_config):
    """Setup CEC capability."""
    from pycec.network import HDMINetwork
    from pycec import CecConfig
    from pycec.commands import CecCommand, KeyReleaseCommand, KeyPressCommand
    from pycec.const import KEY_VOLUME_UP, KEY_VOLUME_DOWN, KEY_MUTE, \
        ADDR_AUDIOSYSTEM, ADDR_BROADCAST, ADDR_UNREGISTERED

    hdmi_network = HDMINetwork(config=CecConfig(name="HASS"), loop=hass.loop)

    def _volume(call):
        """Increase/decrease volume and mute/unmute system."""
        for cmd, att in call.data.items():
            att = 1 if att < 1 else att
            if cmd == CMD_UP:
                for _ in range(att):
                    hdmi_network.send_command(
                        KeyPressCommand(KEY_VOLUME_UP, dst=ADDR_AUDIOSYSTEM))
                    hdmi_network.send_command(
                        KeyReleaseCommand(dst=ADDR_AUDIOSYSTEM))
                _LOGGER.info("Volume increased %d times", att)
            elif cmd == CMD_DOWN:
                for _ in range(att):
                    hdmi_network.send_command(
                        KeyPressCommand(KEY_VOLUME_DOWN, dst=ADDR_AUDIOSYSTEM))
                    hdmi_network.send_command(
                        KeyReleaseCommand(dst=ADDR_AUDIOSYSTEM))
                _LOGGER.info("Volume deceased %d times", att)
            elif cmd == CMD_MUTE:
                hdmi_network.send_command(
                    KeyPressCommand(KEY_MUTE, dst=ADDR_AUDIOSYSTEM))
                hdmi_network.send_command(
                    KeyReleaseCommand(dst=ADDR_AUDIOSYSTEM))
                _LOGGER.info("Audio muted")
            else:
                _LOGGER.warning("Unknown command %s", cmd)

    def _tx(call):
        """Send CEC command."""
        data = call.data
        if ATTR_RAW in data:
            command = CecCommand(data[ATTR_RAW])
        else:
            if ATTR_SRC in data:
                src = data[ATTR_SRC]
            else:
                src = ADDR_UNREGISTERED
            if ATTR_DST in data:
                dst = data[ATTR_DST]
            else:
                dst = ADDR_BROADCAST
            if ATTR_CMD in data:
                cmd = data[ATTR_CMD]
            else:
                _LOGGER.error("Attribute 'cmd' is missing")
                return False
            if ATTR_ATT in data:
                if isinstance(data[ATTR_ATT], (list,)):
                    att = data[ATTR_ATT]
                else:
                    att = reduce(lambda x, y: "%s:%x" % (x, y), data[ATTR_ATT])
            else:
                att = ""
            command = CecCommand(cmd, dst, src, att)
        hdmi_network.send_command(command)

    @callback
    def _standby(call):
        hdmi_network.standby()

    @callback
    def _power_on(call):
        hdmi_network.power_on()

    def _select_device(call):
        """Select the active device."""
        from pycec.datastruct import PhysicalAddress

        addr = call.data[ATTR_DEVICE]
        if not addr:
            _LOGGER.error("Device not found: %s", call.data[ATTR_DEVICE])
            return
        if addr in base_config[DOMAIN][CONF_DEVICES]:
            addr = base_config[DOMAIN][CONF_DEVICES][addr]
        else:
            entity = hass.states.get(addr)
            _LOGGER.debug("Selecting entity %s", entity)
            if entity is not None:
                addr = entity.attributes['physical_address']
                _LOGGER.debug("Address acquired: %s", addr)
                if addr is None:
                    _LOGGER.error("Device %s has not physical address.",
                                  call.data[ATTR_DEVICE])
                    return
        hdmi_network.active_source(PhysicalAddress(addr))
        _LOGGER.info("Selected %s (%s)", call.data[ATTR_DEVICE], addr)

    def _update(call):
        """
        Callback called when device update is needed.

        - called by service, requests CEC network to update data.
        """
        hdmi_network.scan()

    @callback
    def _new_device(device):
        """Called when new device is detected by HDMI network."""
        key = DOMAIN + '.' + device.name
        hass.data[key] = device
        discovery.load_platform(hass, "switch", DOMAIN,
                                discovered={ATTR_NEW: [key]},
                                hass_config=base_config)

    def _shutdown(call):
        hdmi_network.stop()

    def _start_cec(event):
        """Register services and start HDMI network to watch for devices."""
        descriptions = load_yaml_config_file(
            os.path.join(os.path.dirname(__file__), 'services.yaml'))[DOMAIN]
        hass.services.register(DOMAIN, SERVICE_SEND_COMMAND, _tx,
                               descriptions[SERVICE_SEND_COMMAND],
                               SERVICE_SEND_COMMAND_SCHEMA)
        hass.services.register(DOMAIN, SERVICE_VOLUME, _volume,
                               descriptions[SERVICE_VOLUME],
                               SERVICE_VOLUME_SCHEMA)
        hass.services.register(DOMAIN, SERVICE_UPDATE_DEVICES, _update,
                               descriptions[SERVICE_UPDATE_DEVICES],
                               SERVICE_UPDATE_DEVICES_SCHEMA)
        hass.services.register(DOMAIN, SERVICE_POWER_ON, _power_on)
        hass.services.register(DOMAIN, SERVICE_STANDBY, _standby)
        hass.services.register(DOMAIN, SERVICE_SELECT_DEVICE, _select_device)

        hdmi_network.set_new_device_callback(_new_device)
        hdmi_network.start()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, _start_cec)
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, _shutdown)
    return True


class CecDevice(Entity):
    """Representation of a HDMI CEC device entity."""

    def __init__(self, hass: HomeAssistant, device, logical):
        """Initialize the device."""
        self._device = device
        self.hass = hass
        self._icon = None
        self._state = STATE_UNKNOWN
        self._logical_address = logical
        self.entity_id = "%s.%d" % (DOMAIN, self._logical_address)
        device.set_update_callback(self._update)

    def update(self):
        """Update device status."""
        self._update()

    def _update(self, device=None):
        """Update device status."""
        if device:
            if device.power_status == 0:
                self._state = STATE_ON
            elif device.power_status == 1:
                self._state = STATE_OFF
            else:
                _LOGGER.warning("Unknown state: %d", device.power_status)
        self.schedule_update_ha_state()

    @property
    def name(self):
        """Return the name of the device."""
        return (
            "%s %s" % (self.vendor_name, self._device.osd_name)
            if (self._device.osd_name is not None and
                self.vendor_name is not None and self.vendor_name != 'Unknown')
            else "%s %d" % (self._device.type_name, self._logical_address)
            if self._device.osd_name is None
            else "%s %d (%s)" % (self._device.type_name, self._logical_address,
                                 self._device.osd_name))

    @property
    def vendor_id(self):
        """ID of device's vendor."""
        return self._device.vendor_id

    @property
    def vendor_name(self):
        """Name of device's vendor."""
        return self._device.vendor

    @property
    def physical_address(self):
        """Physical address of device in HDMI network."""
        return str(self._device.physical_address)

    @property
    def type(self):
        """String representation of device's type."""
        return self._device.type_name

    @property
    def type_id(self):
        """Type ID of device."""
        return self._device.type

    @property
    def icon(self):
        """Icon for device by its type."""
        return (self._icon if self._icon is not None else
                ICONS_BY_TYPE.get(self._device.type)
                if self._device.type in ICONS_BY_TYPE else ICON_UNKNOWN)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        state_attr = {}
        if self.vendor_id is not None:
            state_attr[ATTR_VENDOR_ID] = self.vendor_id
            state_attr[ATTR_VENDOR_NAME] = self.vendor_name
        if self.type_id is not None:
            state_attr[ATTR_TYPE_ID] = self.type_id
            state_attr[ATTR_TYPE] = self.type
        if self.physical_address is not None:
            state_attr[ATTR_PHYSICAL_ADDRESS] = self.physical_address
        return state_attr
