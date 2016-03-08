"""
Support for RFXtrx switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.rfxtrx/
"""
import logging

import homeassistant.components.rfxtrx as rfxtrx
from homeassistant.components.rfxtrx import (
    ATTR_FIREEVENT, ATTR_NAME, ATTR_PACKETID, ATTR_STATE, EVENT_BUTTON_PRESSED)
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.util import slugify

DEPENDENCIES = ['rfxtrx']
SIGNAL_REPETITIONS = 1

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup the RFXtrx platform."""
    import RFXtrx as rfxtrxmod

    # Add switch from config file
    switchs = []
    signal_repetitions = config.get('signal_repetitions', SIGNAL_REPETITIONS)
    for device_id, entity_info in config.get('devices', {}).items():
        if device_id in rfxtrx.RFX_DEVICES:
            continue
        _LOGGER.info("Add %s rfxtrx.switch", entity_info[ATTR_NAME])

        # Check if i must fire event
        fire_event = entity_info.get(ATTR_FIREEVENT, False)
        datas = {ATTR_STATE: False, ATTR_FIREEVENT: fire_event}

        rfxobject = rfxtrx.get_rfx_object(entity_info[ATTR_PACKETID])
        newswitch = RfxtrxSwitch(
            entity_info[ATTR_NAME], rfxobject, datas,
            signal_repetitions)
        rfxtrx.RFX_DEVICES[device_id] = newswitch
        switchs.append(newswitch)

    add_devices_callback(switchs)

    def switch_update(event):
        """Callback for sensor updates from the RFXtrx gateway."""
        if not isinstance(event.device, rfxtrxmod.LightingDevice) or \
                event.device.known_to_be_dimmable:
            return

        # Add entity if not exist and the automatic_add is True
        device_id = slugify(event.device.id_string.lower())
        if device_id not in rfxtrx.RFX_DEVICES:
            automatic_add = config.get('automatic_add', False)
            if not automatic_add:
                return

            _LOGGER.info(
                "Automatic add %s rfxtrx.switch (Class: %s Sub: %s)",
                device_id,
                event.device.__class__.__name__,
                event.device.subtype
            )
            pkt_id = "".join("{0:02x}".format(x) for x in event.data)
            entity_name = "%s : %s" % (device_id, pkt_id)
            datas = {ATTR_STATE: False, ATTR_FIREEVENT: False}
            signal_repetitions = config.get('signal_repetitions',
                                            SIGNAL_REPETITIONS)
            new_switch = RfxtrxSwitch(entity_name, event, datas,
                                      signal_repetitions)
            rfxtrx.RFX_DEVICES[device_id] = new_switch
            add_devices_callback([new_switch])

        # Check if entity exists or previously added automatically
        if device_id in rfxtrx.RFX_DEVICES:
            _LOGGER.debug(
                "EntityID: %s switch_update. Command: %s",
                device_id,
                event.values['Command']
            )
            if event.values['Command'] == 'On'\
                    or event.values['Command'] == 'Off':

                # Update the rfxtrx device state
                is_on = event.values['Command'] == 'On'
                # pylint: disable=protected-access
                rfxtrx.RFX_DEVICES[device_id]._state = is_on
                rfxtrx.RFX_DEVICES[device_id].update_ha_state()

                # Fire event
                if rfxtrx.RFX_DEVICES[device_id].should_fire_event:
                    rfxtrx.RFX_DEVICES[device_id].hass.bus.fire(
                        EVENT_BUTTON_PRESSED, {
                            ATTR_ENTITY_ID:
                                rfxtrx.RFX_DEVICES[device_id].device_id,
                            ATTR_STATE: event.values['Command'].lower()
                        }
                    )

    # Subscribe to main rfxtrx events
    if switch_update not in rfxtrx.RECEIVED_EVT_SUBSCRIBERS:
        rfxtrx.RECEIVED_EVT_SUBSCRIBERS.append(switch_update)


class RfxtrxSwitch(SwitchDevice):
    """Representation of a RFXtrx switch."""

    def __init__(self, name, event, datas, signal_repetitions):
        """Initialize the switch."""
        self._name = name
        self._event = event
        self._state = datas[ATTR_STATE]
        self._should_fire_event = datas[ATTR_FIREEVENT]
        self.signal_repetitions = signal_repetitions

    @property
    def should_poll(self):
        """No polling needed for a RFXtrx switch."""
        return False

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def should_fire_event(self):
        """Return is the device must fire event."""
        return self._should_fire_event

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._state

    @property
    def assumed_state(self):
        """Return true if unable to access real state of entity."""
        return True

    def turn_on(self, **kwargs):
        """Turn the device on."""
        if not self._event:
            return

        for _ in range(self.signal_repetitions):
            self._event.device.send_on(rfxtrx.RFXOBJECT.transport)

        self._state = True
        self.update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        if not self._event:
            return

        for _ in range(self.signal_repetitions):
            self._event.device.send_off(rfxtrx.RFXOBJECT.transport)

        self._state = False
        self.update_ha_state()
