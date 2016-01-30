"""
homeassistant.components.light.rfxtrx
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for RFXtrx lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.rfxtrx/
"""
import logging
import homeassistant.components.rfxtrx as rfxtrx

from homeassistant.components.light import Light, ATTR_BRIGHTNESS
from homeassistant.util import slugify

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.components.rfxtrx import (
    ATTR_STATE, ATTR_FIREEVENT, ATTR_PACKETID,
    ATTR_NAME, EVENT_BUTTON_PRESSED)


DEPENDENCIES = ['rfxtrx']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Setup the RFXtrx platform. """
    import RFXtrx as rfxtrxmod

    lights = []
    devices = config.get('devices', None)

    if devices:
        for entity_id, entity_info in devices.items():
            if entity_id not in rfxtrx.RFX_DEVICES:
                _LOGGER.info("Add %s rfxtrx.light", entity_info[ATTR_NAME])

                # Check if i must fire event
                fire_event = entity_info.get(ATTR_FIREEVENT, False)
                datas = {ATTR_STATE: False, ATTR_FIREEVENT: fire_event}

                rfxobject = rfxtrx.get_rfx_object(entity_info[ATTR_PACKETID])
                new_light = RfxtrxLight(
                    entity_info[ATTR_NAME], rfxobject, datas
                )
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
            datas = {ATTR_STATE: False, ATTR_FIREEVENT: False}
            new_light = RfxtrxLight(entity_name, event, datas)
            rfxtrx.RFX_DEVICES[entity_id] = new_light
            add_devices_callback([new_light])

        # Check if entity exists or previously added automatically
        if entity_id in rfxtrx.RFX_DEVICES \
                and isinstance(rfxtrx.RFX_DEVICES[entity_id], RfxtrxLight):
            _LOGGER.debug(
                "EntityID: %s light_update. Command: %s",
                entity_id,
                event.values['Command']
            )
            if event.values['Command'] == 'On'\
                    or event.values['Command'] == 'Off':

                # Update the rfxtrx device state
                is_on = event.values['Command'] == 'On'
                # pylint: disable=protected-access
                rfxtrx.RFX_DEVICES[entity_id]._state = is_on
                rfxtrx.RFX_DEVICES[entity_id].update_ha_state()

                # Fire event
                if rfxtrx.RFX_DEVICES[entity_id].should_fire_event:
                    rfxtrx.RFX_DEVICES[entity_id].hass.bus.fire(
                        EVENT_BUTTON_PRESSED, {
                            ATTR_ENTITY_ID:
                                rfxtrx.RFX_DEVICES[entity_id].entity_id,
                            ATTR_STATE: event.values['Command'].lower()
                        }
                    )

    # Subscribe to main rfxtrx events
    if light_update not in rfxtrx.RECEIVED_EVT_SUBSCRIBERS:
        rfxtrx.RECEIVED_EVT_SUBSCRIBERS.append(light_update)


class RfxtrxLight(Light):
    """ Provides a RFXtrx light. """
    def __init__(self, name, event, datas):
        self._name = name
        self._event = event
        self._state = datas[ATTR_STATE]
        self._should_fire_event = datas[ATTR_FIREEVENT]
        self._brightness = 0

    @property
    def should_poll(self):
        """ No polling needed for a light. """
        return False

    @property
    def name(self):
        """ Returns the name of the light if any. """
        return self._name

    @property
    def should_fire_event(self):
        """ Returns is the device must fire event"""
        return self._should_fire_event

    @property
    def is_on(self):
        """ True if light is on. """
        return self._state

    @property
    def brightness(self):
        """ Brightness of this light between 0..255. """
        return self._brightness

    def turn_on(self, **kwargs):
        """ Turn the light on. """
        brightness = kwargs.get(ATTR_BRIGHTNESS)

        if brightness is None:
            self._brightness = 100
        else:
            self._brightness = ((brightness + 4) * 100 // 255 - 1)

        if hasattr(self, '_event') and self._event:
            self._event.device.send_dim(rfxtrx.RFXOBJECT.transport,
                                        self._brightness)

        self._brightness = (self._brightness * 255 // 100)
        self._state = True
        self.update_ha_state()

    def turn_off(self, **kwargs):
        """ Turn the light off. """

        if hasattr(self, '_event') and self._event:
            self._event.device.send_off(rfxtrx.RFXOBJECT.transport)

        self._brightness = 0
        self._state = False
        self.update_ha_state()
