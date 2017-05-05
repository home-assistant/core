"""
Support for Dutch Smart Meter Requirements.

Also known as: Smartmeter or P1 port.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.dsmr/

Technical overview:

DSMR is a standard to which Dutch smartmeters must comply. It specifies that
the smartmeter must send out a 'telegram' every 10 seconds over a serial port.

The contents of this telegram differ between version but they generally consist
of lines with 'obis' (Object Identification System, a numerical ID for a value)
followed with the value and unit.

This module sets up a asynchronous reading loop using the `dsmr_parser` module
which waits for a complete telegram, parser it and puts it on an async queue as
a dictionary of `obis`/object mapping. The numeric value and unit of each value
can be read from the objects attributes. Because the `obis` are know for each
DSMR version the Entities for this component are create during bootstrap.

Another loop (DSMR class) is setup which reads the telegram queue,
stores/caches the latest telegram and notifies the Entities that the telegram
has been updated.
"""
import asyncio
from datetime import timedelta
from functools import partial
import logging

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP, STATE_UNKNOWN)
from homeassistant.core import CoreState
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
import voluptuous as vol

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['dsmr_parser==0.8']

CONF_DSMR_VERSION = 'dsmr_version'
CONF_RECONNECT_INTERVAL = 'reconnect_interval'

DEFAULT_DSMR_VERSION = '2.2'
DEFAULT_PORT = '/dev/ttyUSB0'
DOMAIN = 'dsmr'

ICON_GAS = 'mdi:fire'
ICON_POWER = 'mdi:flash'

# Smart meter sends telegram every 10 seconds
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)
RECONNECT_INTERVAL = 5

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.string,
    vol.Optional(CONF_HOST, default=None): cv.string,
    vol.Optional(CONF_DSMR_VERSION, default=DEFAULT_DSMR_VERSION): vol.All(
        cv.string, vol.In(['4', '2.2'])),
    vol.Optional(CONF_RECONNECT_INTERVAL, default=30): int,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the DSMR sensor."""
    # Suppress logging
    logging.getLogger('dsmr_parser').setLevel(logging.ERROR)

    from dsmr_parser import obis_references as obis_ref
    from dsmr_parser.clients.protocol import (
        create_dsmr_reader, create_tcp_dsmr_reader)
    import serial

    dsmr_version = config[CONF_DSMR_VERSION]

    # Define list of name,obis mappings to generate entities
    obis_mapping = [
        ['Power Consumption', obis_ref.CURRENT_ELECTRICITY_USAGE],
        ['Power Production', obis_ref.CURRENT_ELECTRICITY_DELIVERY],
        ['Power Tariff', obis_ref.ELECTRICITY_ACTIVE_TARIFF],
        ['Power Consumption (low)', obis_ref.ELECTRICITY_USED_TARIFF_1],
        ['Power Consumption (normal)', obis_ref.ELECTRICITY_USED_TARIFF_2],
        ['Power Production (low)', obis_ref.ELECTRICITY_DELIVERED_TARIFF_1],
        ['Power Production (normal)', obis_ref.ELECTRICITY_DELIVERED_TARIFF_2],
    ]

    # Generate device entities
    devices = [DSMREntity(name, obis) for name, obis in obis_mapping]

    # Protocol version specific obis
    if dsmr_version == '4':
        gas_obis = obis_ref.HOURLY_GAS_METER_READING
    else:
        gas_obis = obis_ref.GAS_METER_READING

    # add gas meter reading and derivative for usage
    devices += [
        DSMREntity('Gas Consumption', gas_obis),
        DerivativeDSMREntity('Hourly Gas Consumption', gas_obis),
    ]

    async_add_devices(devices)

    def update_entities_telegram(telegram):
        """Update entities with latests telegram & trigger state update."""
        # Make all device entities aware of new telegram
        for device in devices:
            device.telegram = telegram
            hass.async_add_job(device.async_update_ha_state())

    # Creates a asyncio.Protocol factory for reading DSMR telegrams from serial
    # and calls update_entities_telegram to update entities on arrival
    if config[CONF_HOST]:
        reader_factory = partial(
            create_tcp_dsmr_reader, config[CONF_HOST], config[CONF_PORT],
            config[CONF_DSMR_VERSION], update_entities_telegram,
            loop=hass.loop)
    else:
        reader_factory = partial(
            create_dsmr_reader, config[CONF_PORT], config[CONF_DSMR_VERSION],
            update_entities_telegram, loop=hass.loop)

    @asyncio.coroutine
    def connect_and_reconnect():
        """Connect to DSMR and keep reconnecting until HA stops."""
        while hass.state != CoreState.stopping:
            # Start DSMR asyncio.Protocol reader
            try:
                transport, protocol = yield from hass.loop.create_task(
                    reader_factory())
            except (serial.serialutil.SerialException, ConnectionRefusedError,
                    TimeoutError):
                # log any error while establishing connection and drop to retry
                # connection wait
                _LOGGER.exception("Error connecting to DSMR")
                transport = None

            if transport:
                # register listener to close transport on HA shutdown
                stop_listerer = hass.bus.async_listen_once(
                    EVENT_HOMEASSISTANT_STOP, transport.close)

                # wait for reader to close
                yield from protocol.wait_closed()

            if hass.state != CoreState.stopping:
                # unexpected disconnect
                if transport:
                    # remove listerer
                    stop_listerer()

                # reflect disconnect state in devices state by setting an
                # empty telegram resulting in `unkown` states
                update_entities_telegram({})

                # throttle reconnect attempts
                yield from asyncio.sleep(config[CONF_RECONNECT_INTERVAL],
                                         loop=hass.loop)

    # Cannot be hass.async_add_job because job runs forever
    hass.loop.create_task(connect_and_reconnect())


class DSMREntity(Entity):
    """Entity reading values from DSMR telegram."""

    def __init__(self, name, obis):
        """Initialize entity."""
        self._name = name
        self._obis = obis
        self.telegram = {}

    def get_dsmr_object_attr(self, attribute):
        """Read attribute from last received telegram for this DSMR object."""
        # Make sure telegram contains an object for this entities obis
        if self._obis not in self.telegram:
            return None

        # get the attibute value if the object has it
        dsmr_object = self.telegram[self._obis]
        return getattr(dsmr_object, attribute, None)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        if 'Power' in self._name:
            return ICON_POWER
        elif 'Gas' in self._name:
            return ICON_GAS

    @property
    def state(self):
        """Return the state of sensor, if available, translate if needed."""
        from dsmr_parser import obis_references as obis

        value = self.get_dsmr_object_attr('value')

        if self._obis == obis.ELECTRICITY_ACTIVE_TARIFF:
            return self.translate_tariff(value)
        else:
            if value is not None:
                return value
            else:
                return STATE_UNKNOWN

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self.get_dsmr_object_attr('unit')

    @staticmethod
    def translate_tariff(value):
        """Convert 2/1 to normal/low."""
        # DSMR V2.2: Note: Rate code 1 is used for low rate and rate code 2 is
        # used for normal rate.
        if value == '0002':
            return 'normal'
        elif value == '0001':
            return 'low'
        else:
            return STATE_UNKNOWN


class DerivativeDSMREntity(DSMREntity):
    """Calculated derivative for values where the DSMR doesn't offer one.

    Gas readings are only reported per hour and don't offer a rate only
    the current meter reading. This entity converts subsequents readings
    into a hourly rate.

    """

    _previous_reading = None
    _previous_timestamp = None
    _state = STATE_UNKNOWN

    @property
    def state(self):
        """Return the calculated current hourly rate."""
        return self._state

    @asyncio.coroutine
    def async_update(self):
        """Recalculate hourly rate if timestamp has changed.

        DSMR updates gas meter reading every hour. Along with the new
        value a timestamp is provided for the reading. Test if the last
        known timestamp differs from the current one then calculate a
        new rate for the previous hour.

        """
        # check if the timestamp for the object differs from the previous one
        timestamp = self.get_dsmr_object_attr('datetime')
        if timestamp and timestamp != self._previous_timestamp:
            current_reading = self.get_dsmr_object_attr('value')

            if self._previous_reading is None:
                # can't calculate rate without previous datapoint
                # just store current point
                pass
            else:
                # recalculate the rate
                diff = current_reading - self._previous_reading
                self._state = diff

            self._previous_reading = current_reading
            self._previous_timestamp = timestamp

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, per hour, if any."""
        unit = self.get_dsmr_object_attr('unit')
        if unit:
            return unit + '/h'
