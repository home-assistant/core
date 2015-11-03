"""
homeassistant.components.light.rfxtrx
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for RFXtrx lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.rfxtrx.html
"""
import logging
import homeassistant.components.rfxtrx as rfxtrx
import RFXtrx as rfxtrxmod

from homeassistant.components.light import Light
from homeassistant.util import slugify

DEPENDENCIES = ['rfxtrx']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Setup the RFXtrx platform. """
    lights = []
    devices = config.get('devices', None)
    if devices:
        for entity_id, entity_info in devices.items():
            if entity_id not in rfxtrx.RFX_DEVICES:
                _LOGGER.info("Add %s rfxtrx.light", entity_info['name'])
                rfxobject = rfxtrx.get_rfx_object(entity_info['packetid'])
                new_light = RfxtrxLight(entity_info['name'], rfxobject, False)
                rfxtrx.RFX_DEVICES[entity_id] = new_light
                lights.append(new_light)

    add_devices_callback(lights)

    def light_update(event):
        """ Callback for light updates from the RFXtrx gateway. """
        if not isinstance(event.device, rfxtrxmod.LightingDevice):
            return

        # Add entity if not exist and the automatic_add is True
        entity_id = slugify(event.device.id_string.lower())
        if entity_id not in rfxtrx.RFX_DEVICES:
            automatic_add = config.get('automatic_add', False)
            if not automatic_add:
                return

            _LOGGER.info(
                "Automatic add %s rfxtrx.light (Class: %s Sub: %s)",
                entity_id,
                event.device.__class__.__name__,
                event.device.subtype
            )
            pkt_id = "".join("{0:02x}".format(x) for x in event.data)
            entity_name = "%s : %s" % (entity_id, pkt_id)
            new_light = RfxtrxLight(entity_name, event, False)
            rfxtrx.RFX_DEVICES[entity_id] = new_light
            add_devices_callback([new_light])

        # Check if entity exists or previously added automatically
        if entity_id in rfxtrx.RFX_DEVICES:
            if event.values['Command'] == 'On'\
                    or event.values['Command'] == 'Off':
                if event.values['Command'] == 'On':
                    rfxtrx.RFX_DEVICES[entity_id].turn_on()
                else:
                    rfxtrx.RFX_DEVICES[entity_id].turn_off()

    # Subscribe to main rfxtrx events
    if light_update not in rfxtrx.RECEIVED_EVT_SUBSCRIBERS:
        rfxtrx.RECEIVED_EVT_SUBSCRIBERS.append(light_update)


class RfxtrxLight(Light):
    """ Provides a RFXtrx light. """
    def __init__(self, name, event, state):
        self._name = name
        self._event = event
        self._state = state

    @property
    def should_poll(self):
        """ No polling needed for a light. """
        return False

    @property
    def name(self):
        """ Returns the name of the light if any. """
        return self._name

    @property
    def is_on(self):
        """ True if light is on. """
        return self._state

    def turn_on(self, **kwargs):
        """ Turn the light on. """

        if hasattr(self, '_event') and self._event:
            self._event.device.send_on(rfxtrx.RFXOBJECT.transport)

        self._state = True
        self.update_ha_state()

    def turn_off(self, **kwargs):
        """ Turn the light off. """

        if hasattr(self, '_event') and self._event:
            self._event.device.send_off(rfxtrx.RFXOBJECT.transport)

        self._state = False
        self.update_ha_state()
