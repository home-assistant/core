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

import logging
from datetime import timedelta
import asyncio
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_DEVICE, EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.entity import Entity

DOMAIN = 'dsmr'

REQUIREMENTS = ['dsmr-parser==0.3']

# Smart meter sends telegram every 10 seconds
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)

CONF_DSMR_VERSION = 'dsmr_version'
DEFAULT_DEVICE = '/dev/ttyUSB0'
DEFAULT_DSMR_VERSION = '2.2'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_DEVICE, default=DEFAULT_DEVICE): cv.string,
    vol.Optional(CONF_DSMR_VERSION, default=DEFAULT_DSMR_VERSION): vol.All(
        cv.string, vol.In(['4', '2.2'])),
})

_LOGGER = logging.getLogger(__name__)

ICON_POWER = 'mdi:flash'
ICON_GAS = 'mdi:fire'


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup DSMR sensors."""
    # suppres logging
    logging.getLogger('dsmr_parser').setLevel(logging.ERROR)

    from dsmr_parser import obis_references as obis

    dsmr_version = config[CONF_DSMR_VERSION]

    # define list of name,obis mappings to generate entities
    obis_mapping = [
        ['Power Consumption', obis.CURRENT_ELECTRICITY_USAGE],
        ['Power Production', obis.CURRENT_ELECTRICITY_DELIVERY],
        ['Power Tariff', obis.ELECTRICITY_ACTIVE_TARIFF],
        ['Power Consumption (normal)', obis.ELECTRICITY_USED_TARIFF_1],
        ['Power Consumption (low)', obis.ELECTRICITY_USED_TARIFF_2],
        ['Power Production (normal)', obis.ELECTRICITY_DELIVERED_TARIFF_1],
        ['Power Production (low)', obis.ELECTRICITY_DELIVERED_TARIFF_1],
    ]
    # protocol version specific obis
    if dsmr_version == '4':
        obis_mapping.append(['Gas Consumption', obis.HOURLY_GAS_METER_READING])
    else:
        obis_mapping.append(['Gas Consumption', obis.GAS_METER_READING])

    # make list available early to allow cross referencing dsmr/entities
    devices = []

    # queue for receiving parsed telegrams from async dsmr reader
    queue = asyncio.Queue()

    # create DSMR interface
    dsmr = DSMR(hass, config, devices, queue)

    # generate device entities
    devices += [DSMREntity(name, obis, dsmr) for name, obis in obis_mapping]

    # setup devices
    yield from async_add_devices(devices)

    # add asynchronous serial reader/parser task
    reader = hass.loop.create_task(dsmr.dsmr_parser.read(queue))

    # serial telegram reader is a infinite looping task, it will only resolve
    # when it has an exception, in that case log this.
    def handle_error(future):
        """If result is an exception log it."""
        _LOGGER.error('error during initialization of DSMR serial reader: %s',
                      future.exception())
    reader.add_done_callback(handle_error)

    # add task to receive telegrams and update entities
    hass.async_add_job(dsmr.read_telegrams)


class DSMR:
    """DSMR interface."""

    def __init__(self, hass, config, devices, queue):
        """Setup DSMR serial interface, initialize, add device entity list."""
        from dsmr_parser.serial import (
            SERIAL_SETTINGS_V4,
            SERIAL_SETTINGS_V2_2,
            AsyncSerialReader
        )
        from dsmr_parser import telegram_specifications

        # map dsmr version to settings
        dsmr_versions = {
            '4': (SERIAL_SETTINGS_V4, telegram_specifications.V4),
            '2.2': (SERIAL_SETTINGS_V2_2, telegram_specifications.V2_2),
        }

        # initialize asynchronous telegram reader
        dsmr_version = config[CONF_DSMR_VERSION]
        self.dsmr_parser = AsyncSerialReader(
            device=config[CONF_DEVICE],
            serial_settings=dsmr_versions[dsmr_version][0],
            telegram_specification=dsmr_versions[dsmr_version][1],
        )

        # keep list of device entities to update
        self.devices = devices

        self._queue = queue

        # initialize empty telegram
        self._telegram = {}

        # forward stop event to reading loop
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP,
                                   self._queue.put_nowait)

    @asyncio.coroutine
    def read_telegrams(self):
        """Receive parsed telegram from DSMR reader, update entities."""
        while True:
            # asynchronously get latest telegram when it arrives
            event = yield from self._queue.get()

            # stop loop if stop event was received
            if getattr(event, 'event_type', None) == EVENT_HOMEASSISTANT_STOP:
                self._queue.task_done()
                return

            self._telegram = event
            _LOGGER.debug('received DSMR telegram')

            # make all device entities aware of new telegram
            for device in self.devices:
                yield from device.async_update_ha_state()

    @property
    def telegram(self):
        """Return telegram object."""
        return self._telegram


class DSMREntity(Entity):
    """Entity reading values from DSMR telegram."""

    def __init__(self, name, obis, interface):
        """"Initialize entity."""
        # human readable name
        self._name = name
        # DSMR spec. value identifier
        self._obis = obis
        # interface class to get telegram data
        self._interface = interface

    def get_dsmr_object_attr(self, attribute):
        """Read attribute from last received telegram for this DSMR object."""
        # get most recent cached telegram from interface
        telegram = self._interface.telegram

        # make sure telegram contains an object for this entities obis
        if self._obis not in telegram:
            return None

        # get the attibute value if the object has it
        dsmr_object = telegram[self._obis]
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
        # DSMR V2.2: Note: Tariff code 1 is used for low tariff
        # and tariff code 2 is used for normal tariff.

        if value == '0002':
            return 'normal'
        elif value == '0001':
            return 'low'
        else:
            return None
