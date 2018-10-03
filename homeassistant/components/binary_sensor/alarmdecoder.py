"""
Support for AlarmDecoder zone states- represented as binary sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.alarmdecoder/
"""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.alarmdecoder import (
    ZONE_SCHEMA, CONF_ZONES, CONF_ZONE_NAME, CONF_ZONE_TYPE,
    CONF_ZONE_RFID, SIGNAL_ZONE_FAULT, SIGNAL_ZONE_RESTORE,
    SIGNAL_RFX_MESSAGE, SIGNAL_REL_MESSAGE, CONF_RELAY_ADDR,
    CONF_RELAY_CHAN)

DEPENDENCIES = ['alarmdecoder']

_LOGGER = logging.getLogger(__name__)

ATTR_RF_BIT0 = 'rf_bit0'
ATTR_RF_LOW_BAT = 'rf_low_battery'
ATTR_RF_SUPERVISED = 'rf_supervised'
ATTR_RF_BIT3 = 'rf_bit3'
ATTR_RF_LOOP3 = 'rf_loop3'
ATTR_RF_LOOP2 = 'rf_loop2'
ATTR_RF_LOOP4 = 'rf_loop4'
ATTR_RF_LOOP1 = 'rf_loop1'


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the AlarmDecoder binary sensor devices."""
    configured_zones = discovery_info[CONF_ZONES]

    devices = []
    for zone_num in configured_zones:
        device_config_data = ZONE_SCHEMA(configured_zones[zone_num])
        zone_type = device_config_data[CONF_ZONE_TYPE]
        zone_name = device_config_data[CONF_ZONE_NAME]
        zone_rfid = device_config_data.get(CONF_ZONE_RFID)
        relay_addr = device_config_data.get(CONF_RELAY_ADDR)
        relay_chan = device_config_data.get(CONF_RELAY_CHAN)
        device = AlarmDecoderBinarySensor(
            zone_num, zone_name, zone_type, zone_rfid, relay_addr, relay_chan)
        devices.append(device)

    add_entities(devices)

    return True


class AlarmDecoderBinarySensor(BinarySensorDevice):
    """Representation of an AlarmDecoder binary sensor."""

    def __init__(self, zone_number, zone_name, zone_type, zone_rfid,
                 relay_addr, relay_chan):
        """Initialize the binary_sensor."""
        self._zone_number = zone_number
        self._zone_type = zone_type
        self._state = None
        self._name = zone_name
        self._rfid = zone_rfid
        self._rfstate = None
        self._relay_addr = relay_addr
        self._relay_chan = relay_chan

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.hass.helpers.dispatcher.async_dispatcher_connect(
            SIGNAL_ZONE_FAULT, self._fault_callback)

        self.hass.helpers.dispatcher.async_dispatcher_connect(
            SIGNAL_ZONE_RESTORE, self._restore_callback)

        self.hass.helpers.dispatcher.async_dispatcher_connect(
            SIGNAL_RFX_MESSAGE, self._rfx_message_callback)

        self.hass.helpers.dispatcher.async_dispatcher_connect(
            SIGNAL_REL_MESSAGE, self._rel_message_callback)

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attr = {}
        if self._rfid and self._rfstate is not None:
            attr[ATTR_RF_BIT0] = True if self._rfstate & 0x01 else False
            attr[ATTR_RF_LOW_BAT] = True if self._rfstate & 0x02 else False
            attr[ATTR_RF_SUPERVISED] = True if self._rfstate & 0x04 else False
            attr[ATTR_RF_BIT3] = True if self._rfstate & 0x08 else False
            attr[ATTR_RF_LOOP3] = True if self._rfstate & 0x10 else False
            attr[ATTR_RF_LOOP2] = True if self._rfstate & 0x20 else False
            attr[ATTR_RF_LOOP4] = True if self._rfstate & 0x40 else False
            attr[ATTR_RF_LOOP1] = True if self._rfstate & 0x80 else False
        return attr

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._state == 1

    @property
    def device_class(self):
        """Return the class of this sensor, from DEVICE_CLASSES."""
        return self._zone_type

    def _fault_callback(self, zone):
        """Update the zone's state, if needed."""
        if zone is None or int(zone) == self._zone_number:
            self._state = 1
            self.schedule_update_ha_state()

    def _restore_callback(self, zone):
        """Update the zone's state, if needed."""
        if zone is None or int(zone) == self._zone_number:
            self._state = 0
            self.schedule_update_ha_state()

    def _rfx_message_callback(self, message):
        """Update RF state."""
        if self._rfid and message and message.serial_number == self._rfid:
            self._rfstate = message.value
            self.schedule_update_ha_state()

    def _rel_message_callback(self, message):
        """Update relay state."""
        if (self._relay_addr == message.address and
                self._relay_chan == message.channel):
            _LOGGER.debug("Relay %d:%d value:%d", message.address,
                          message.channel, message.value)
            self._state = message.value
            self.schedule_update_ha_state()
