"""
HDMI CEC component.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/hdmi_cec/
"""
import logging

import os
import voluptuous as vol
from collections import defaultdict
from functools import reduce

from homeassistant.components import discovery
from homeassistant.config import load_yaml_config_file
from homeassistant.const import (EVENT_HOMEASSISTANT_START, STATE_UNKNOWN,
                                 EVENT_HOMEASSISTANT_STOP, STATE_ON,
                                 STATE_OFF)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['pyCEC>=0.2.1']

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

SERVICE_SELECT_DEVICE = 'select_device'
SERVICE_SEND_COMMAND = 'send_command'
SERVICE_VOLUME = 'volume'
SERVICE_UPDATE_DEVICES = 'update'

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

SERVICE_SEND_COMMAND_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(ATTR_CMD): vol.Coerce(int),
        vol.Optional(ATTR_SRC): vol.Coerce(int),
        vol.Optional(ATTR_DST): vol.Coerce(int),
        vol.Optional(ATTR_ATT): vol.Coerce(int),
        vol.Optional(ATTR_RAW): vol.Coerce(str)
    })
}, extra=vol.REMOVE_EXTRA)

SERVICE_VOLUME_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CMD_UP): vol.Coerce(int),
        vol.Optional(CMD_DOWN): vol.Coerce(int),
        vol.Optional(CMD_MUTE): None,
        vol.Optional(CMD_UNMUTE): None,
        vol.Optional(CMD_MUTE_TOGGLE): None
    })
}, extra=vol.REMOVE_EXTRA)

SERVICE_POWER_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(ATTR_DST): vol.Coerce(int),
    })
}, extra=vol.REMOVE_EXTRA)


def setup(hass: HomeAssistant, base_config):
    """Setup CEC capability."""
    from pycec.network import HDMINetwork
    from pycec import CecConfig
    from pycec.commands import CecCommand, KeyReleaseCommand, KeyPressCommand
    from pycec.const import KEY_VOLUME_UP, KEY_VOLUME_DOWN, KEY_MUTE, \
        ADDR_AUDIOSYSTEM, ADDR_BROADCAST, ADDR_UNREGISTERED

    hdmi_network = HDMINetwork(config=CecConfig(name="HA"), loop=hass.loop)

    @callback
    def _volume(call):
        """Increase/decrease volume and mute/unmute system."""
        for cmd, att in call.data.items():
            att = int(att)
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
                hdmi_network.send_command(KeyReleaseCommand(dst=ADDR_AUDIOSYSTEM))
                _LOGGER.info("Audio muted")
            else:
                _LOGGER.warning("Unknown command %s", cmd)

    @callback
    def _tx(call):
        """Send CEC command."""
        d = call.data
        if ATTR_RAW in d:
            command = CecCommand(d[ATTR_RAW])
        else:
            if ATTR_SRC in d:
                src = d[ATTR_SRC]
            else:
                src = ADDR_UNREGISTERED
            if ATTR_DST in d:
                dst = d[ATTR_DST]
            else:
                dst = ADDR_BROADCAST
            if ATTR_CMD in d:
                cmd = d[ATTR_CMD]
            else:
                _LOGGER.error("Attribute 'cmd' is missing")
                return False
            if ATTR_ATT in d:
                if isinstance(d[ATTR_ATT], (list,)):
                    att = d[ATTR_ATT]
                else:
                    att = reduce(lambda x, y: "%s:%x" % (x, y), d[ATTR_ATT])
            else:
                att = ""
            command = CecCommand(cmd, dst, src, att)
        hdmi_network.send_command(command)

    @callback
    def _update(call):
        """
        Callback called when device update is needed.

        - called by service, requests CEC network to update data.
        """
        hdmi_network.scan()

    @callback
    def _new_device(device):
        """Called when new device is detected by HDMI network."""
        discovery.load_platform(hass, "switch", DOMAIN,
                                discovered={ATTR_NEW: [device]},
                                hass_config=base_config)

    def _start_cec(event):
        """Register services and start HDMI network to watch for devices."""
        descriptions = load_yaml_config_file(
            os.path.join(os.path.dirname(__file__), 'services.yaml'))[DOMAIN]
        hass.services.register(DOMAIN, SERVICE_SEND_COMMAND, _tx,
                               descriptions[SERVICE_SEND_COMMAND])
        hass.services.register(DOMAIN, SERVICE_VOLUME, _volume,
                               descriptions[SERVICE_VOLUME])
        hass.services.register(DOMAIN, SERVICE_UPDATE_DEVICES, _update)
        hdmi_network.set_new_device_callback(_new_device)
        hdmi_network.start()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, _start_cec)
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, hdmi_network.stop)
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
        device.set_update_callback(self.update)

    def update(self, device=None):
        """Updates device status."""
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
        return "%s %s" % (
            self.vendor_name, self._device.osd_name) \
            if self._device.osd_name is not None and \
            self.vendor_name is not None and self.vendor_name != 'Unknown' \
            else "%s %d" % (self._device.type_name,
                            self._logical_address) \
            if self._device.osd_name is None \
            else "%s %d (%s)" % (
                self._device.type_name, self._logical_address,
                self._device.osd_name)

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
        return self._icon if self._icon is not None \
            else ICONS_BY_TYPE.get(
                self._device.type) if self._device.type in ICONS_BY_TYPE \
            else ICON_UNKNOWN

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
