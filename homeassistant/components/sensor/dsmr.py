"""
Support for Dutch Smart Meter (also known as Smartmeter or P1 port).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.dsmr/
"""
import asyncio
from datetime import timedelta
from functools import partial
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP, STATE_UNKNOWN)
from homeassistant.core import CoreState
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['dsmr_parser==0.11']

CONF_DSMR_VERSION = 'dsmr_version'
CONF_RECONNECT_INTERVAL = 'reconnect_interval'

DEFAULT_DSMR_VERSION = '2.2'
DEFAULT_PORT = '/dev/ttyUSB0'
DOMAIN = 'dsmr'

ICON_GAS = 'mdi:fire'
ICON_POWER = 'mdi:flash'
ICON_POWER_FAILURE = 'mdi:flash-off'
ICON_SWELL_SAG = 'mdi:pulse'

# Smart meter sends telegram every 10 seconds
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)

RECONNECT_INTERVAL = 5

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.string,
    vol.Optional(CONF_HOST): cv.string,
    vol.Optional(CONF_DSMR_VERSION, default=DEFAULT_DSMR_VERSION): vol.All(
        cv.string, vol.In(['5', '4', '2.2'])),
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
        [
            'Power Consumption',
            obis_ref.CURRENT_ELECTRICITY_USAGE
        ],
        [
            'Power Production',
            obis_ref.CURRENT_ELECTRICITY_DELIVERY
        ],
        [
            'Power Tariff',
            obis_ref.ELECTRICITY_ACTIVE_TARIFF
        ],
        [
            'Power Consumption (low)',
            obis_ref.ELECTRICITY_USED_TARIFF_1
        ],
        [
            'Power Consumption (normal)',
            obis_ref.ELECTRICITY_USED_TARIFF_2
        ],
        [
            'Power Production (low)',
            obis_ref.ELECTRICITY_DELIVERED_TARIFF_1
        ],
        [
            'Power Production (normal)',
            obis_ref.ELECTRICITY_DELIVERED_TARIFF_2
        ],
        [
            'Power Consumption Phase L1',
            obis_ref.INSTANTANEOUS_ACTIVE_POWER_L1_POSITIVE
        ],
        [
            'Power Consumption Phase L2',
            obis_ref.INSTANTANEOUS_ACTIVE_POWER_L2_POSITIVE
        ],
        [
            'Power Consumption Phase L3',
            obis_ref.INSTANTANEOUS_ACTIVE_POWER_L3_POSITIVE
        ],
        [
            'Power Production Phase L1',
            obis_ref.INSTANTANEOUS_ACTIVE_POWER_L1_NEGATIVE
        ],
        [
            'Power Production Phase L2',
            obis_ref.INSTANTANEOUS_ACTIVE_POWER_L2_NEGATIVE
        ],
        [
            'Power Production Phase L3',
            obis_ref.INSTANTANEOUS_ACTIVE_POWER_L3_NEGATIVE
        ],
        [
            'Long Power Failure Count',
            obis_ref.LONG_POWER_FAILURE_COUNT
        ],
        [
            'Voltage Sags Phase L1',
            obis_ref.VOLTAGE_SAG_L1_COUNT
        ],
        [
            'Voltage Sags Phase L2',
            obis_ref.VOLTAGE_SAG_L2_COUNT
        ],
        [
            'Voltage Sags Phase L3',
            obis_ref.VOLTAGE_SAG_L3_COUNT
        ],
        [
            'Voltage Swells Phase L1',
            obis_ref.VOLTAGE_SWELL_L1_COUNT
        ],
        [
            'Voltage Swells Phase L2',
            obis_ref.VOLTAGE_SWELL_L2_COUNT
        ],
        [
            'Voltage Swells Phase L3',
            obis_ref.VOLTAGE_SWELL_L3_COUNT
        ],
    ]

    # Generate device entities
    devices = [DSMREntity(name, obis) for name, obis in obis_mapping]

    # Protocol version specific obis
    if dsmr_version in ('4', '5'):
        gas_obis = obis_ref.HOURLY_GAS_METER_READING
    else:
        gas_obis = obis_ref.GAS_METER_READING

    # Add gas meter reading and derivative for usage
    devices += [
        DSMREntity('Gas Consumption', gas_obis),
        DerivativeDSMREntity('Hourly Gas Consumption', gas_obis),
    ]

    async_add_devices(devices)

    def update_entities_telegram(telegram):
        """Update entities with latest telegram and trigger state update."""
        # Make all device entities aware of new telegram
        for device in devices:
            device.telegram = telegram
            hass.async_add_job(device.async_update_ha_state())

    # Creates an asyncio.Protocol factory for reading DSMR telegrams from
    # serial and calls update_entities_telegram to update entities on arrival
    if CONF_HOST in config:
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
        """Connect to DSMR and keep reconnecting until Home Assistant stops."""
        while hass.state != CoreState.stopping:
            # Start DSMR asyncio.Protocol reader
            try:
                transport, protocol = yield from hass.loop.create_task(
                    reader_factory())
            except (serial.serialutil.SerialException, ConnectionRefusedError,
                    TimeoutError):
                # Log any error while establishing connection and drop to retry
                # connection wait
                _LOGGER.exception("Error connecting to DSMR")
                transport = None

            if transport:
                # Register listener to close transport on HA shutdown
                stop_listener = hass.bus.async_listen_once(
                    EVENT_HOMEASSISTANT_STOP, transport.close)

                # Wait for reader to close
                yield from protocol.wait_closed()

            if hass.state != CoreState.stopping:
                # Unexpected disconnect
                if transport:
                    # remove listener
                    stop_listener()

                # Reflect disconnect state in devices state by setting an
                # empty telegram resulting in `unknown` states
                update_entities_telegram({})

                # throttle reconnect attempts
                yield from asyncio.sleep(config[CONF_RECONNECT_INTERVAL],
                                         loop=hass.loop)

    # Can't be hass.async_add_job because job runs forever
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

        # Get the attribute value if the object has it
        dsmr_object = self.telegram[self._obis]
        return getattr(dsmr_object, attribute, None)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        if 'Sags' in self._name or 'Swells' in self.name:
            return ICON_SWELL_SAG
        if 'Failure' in self._name:
            return ICON_POWER_FAILURE
        if 'Power' in self._name:
            return ICON_POWER
        if 'Gas' in self._name:
            return ICON_GAS

    @property
    def state(self):
        """Return the state of sensor, if available, translate if needed."""
        from dsmr_parser import obis_references as obis

        value = self.get_dsmr_object_attr('value')

        if self._obis == obis.ELECTRICITY_ACTIVE_TARIFF:
            return self.translate_tariff(value)

        if value is not None:
            return value

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
        if value == '0001':
            return 'low'

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
                # Can't calculate rate without previous datapoint
                # just store current point
                pass
            else:
                # Recalculate the rate
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
