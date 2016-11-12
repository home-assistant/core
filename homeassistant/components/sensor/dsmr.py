"""
Support for Dutch Smart Meter Requirements.

Also known as: Smartmeter or P1 port.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.dsmr/
"""

import logging
from datetime import timedelta
import asyncio
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_DEVICE
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

    # create DSMR interface
    dsmr = DSMR(hass, config, devices)

    # generate device entities
    devices += [DSMREntity(name, obis, dsmr) for name, obis in obis_mapping]

    # setup devices
    yield from hass.loop.create_task(async_add_devices(devices))

    # queue for receiving parsed telegrams from async dsmr reader
    queue = asyncio.Queue()

    # add asynchronous serial reader/parser task
    hass.loop.create_task(dsmr.dsmr_parser.read(queue))

    # add task to receive telegrams and update entities
    hass.loop.create_task(dsmr.read_telegrams(queue))


class DSMR:
    """DSMR interface."""

    def __init__(self, hass, config, devices):
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

        # initialize empty telegram
        self._telegram = {}

    @asyncio.coroutine
    def read_telegrams(self, queue):
        """Receive parsed telegram from DSMR reader, update entities."""
        while True:
            # asynchronously get latest telegram when it arrives
            self._telegram = yield from queue.get()
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

        value = getattr(self._interface.telegram.get(self._obis, {}),
                        'value', None)

        if self._obis == obis.ELECTRICITY_ACTIVE_TARIFF:
            return self.translate_tariff(value)
        else:
            return value

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return getattr(self._interface.telegram.get(self._obis, {}),
                       'unit', None)

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


class DSMRTariff(DSMREntity):
    """Convert integer tariff value to text."""

    @property
    def state(self):
        """Convert 2/1 to normal/low."""
        # DSMR V2.2: Note: Tariff code 1 is used for low tariff
        # and tariff code 2 is used for normal tariff.

        tariff = super().state
        if tariff == '0002':
            return 'normal'
        elif tariff == '0001':
            return 'low'
        else:
            return None
