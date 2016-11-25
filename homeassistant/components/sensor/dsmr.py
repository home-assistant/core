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
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_PORT, EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['dsmr_parser==0.4']

CONF_DSMR_VERSION = 'dsmr_version'

DEFAULT_DSMR_VERSION = '2.2'
DEFAULT_PORT = '/dev/ttyUSB0'
DOMAIN = 'dsmr'

ICON_GAS = 'mdi:fire'
ICON_POWER = 'mdi:flash'

# Smart meter sends telegram every 10 seconds
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.string,
    vol.Optional(CONF_DSMR_VERSION, default=DEFAULT_DSMR_VERSION): vol.All(
        cv.string, vol.In(['4', '2.2'])),
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the DSMR sensor."""
    # Suppress logging
    logging.getLogger('dsmr_parser').setLevel(logging.ERROR)

    from dsmr_parser import obis_references as obis
    from dsmr_parser.protocol import create_dsmr_reader

    dsmr_version = config[CONF_DSMR_VERSION]

    # Define list of name,obis mappings to generate entities
    obis_mapping = [
        ['Power Consumption', obis.CURRENT_ELECTRICITY_USAGE],
        ['Power Production', obis.CURRENT_ELECTRICITY_DELIVERY],
        ['Power Tariff', obis.ELECTRICITY_ACTIVE_TARIFF],
        ['Power Consumption (low)', obis.ELECTRICITY_USED_TARIFF_1],
        ['Power Consumption (normal)', obis.ELECTRICITY_USED_TARIFF_2],
        ['Power Production (low)', obis.ELECTRICITY_DELIVERED_TARIFF_1],
        ['Power Production (normal)', obis.ELECTRICITY_DELIVERED_TARIFF_2],
    ]
    # Protocol version specific obis
    if dsmr_version == '4':
        obis_mapping.append(['Gas Consumption', obis.HOURLY_GAS_METER_READING])
    else:
        obis_mapping.append(['Gas Consumption', obis.GAS_METER_READING])

    # Generate device entities
    devices = [DSMREntity(name, obis) for name, obis in obis_mapping]

    yield from async_add_devices(devices)

    def update_entities_telegram(telegram):
        """Update entities with latests telegram & trigger state update."""
        # Make all device entities aware of new telegram
        for device in devices:
            device.telegram = telegram
            hass.async_add_job(device.async_update_ha_state)

    # Creates a asyncio.Protocol for reading DSMR telegrams from serial
    # and calls update_entities_telegram to update entities on arrival
    dsmr = create_dsmr_reader(config[CONF_PORT], config[CONF_DSMR_VERSION],
                              update_entities_telegram, loop=hass.loop)

    # Start DSMR asycnio.Protocol reader
    transport, _ = yield from hass.loop.create_task(dsmr)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, transport.close)


class DSMREntity(Entity):
    """Entity reading values from DSMR telegram."""

    def __init__(self, name, obis):
        """"Initialize entity."""
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
            return value

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
            return None
