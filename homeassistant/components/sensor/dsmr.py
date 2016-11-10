"""
Support for Dutch Smart Meter Requirements.

Also known as: Smartmeter or P1 port.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.dsmr/
"""

import logging
from datetime import timedelta

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_DEVICE
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

DOMAIN = 'dsmr'

REQUIREMENTS = ['dsmr-parser==0.2']

# Smart meter sends telegram every 10 seconds
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)

CONF_DSMR_VERSION = 'dsmr_version'
DEFAULT_DEVICE = '/dev/ttyUSB0'
DEFAULT_DSMR_VERSION = '4'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_DEVICE, default=DEFAULT_DEVICE): cv.string,
    vol.Optional(CONF_DSMR_VERSION, default=DEFAULT_DSMR_VERSION): vol.All(
        cv.string, vol.In(['4', '2.2'])),
})

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup DSMR sensors."""
    from dsmr_parser import obis_references as obis

    devices = []

    dsmr = DSMR(hass, config, devices)

    devices += [
        DSMREntity('Power Consumption', obis.CURRENT_ELECTRICITY_USAGE, dsmr),
        DSMREntity('Power Production', obis.CURRENT_ELECTRICITY_DELIVERY, dsmr),
        DSMRTariff('Power Tariff', obis.ELECTRICITY_ACTIVE_TARIFF, dsmr),
        DSMREntity('Power Consumption (normal)', obis.ELECTRICITY_USED_TARIFF_1, dsmr),
        DSMREntity('Power Consumption (low)', obis.ELECTRICITY_USED_TARIFF_2, dsmr),
        DSMREntity('Power Production (normal)', obis.ELECTRICITY_DELIVERED_TARIFF_1, dsmr),
        DSMREntity('Power Production (low)', obis.ELECTRICITY_DELIVERED_TARIFF_1, dsmr),
    ]
    dsmr_version = config[CONF_DSMR_VERSION]
    if dsmr_version == '4':
        devices.append(DSMREntity('Gas Consumption', obis.HOURLY_GAS_METER_READING, dsmr))
    else:
        devices.append(DSMREntity('Gas Consumption', obis.GAS_METER_READING, dsmr))

    add_devices(devices)


class DSMR:
    """DSMR interface."""

    def __init__(self, hass, config, devices):
        """Setup DSMR serial interface and add device entities."""
        from dsmr_parser.serial import (
            SERIAL_SETTINGS_V4,
            SERIAL_SETTINGS_V2_2,
            SerialReader
        )
        from dsmr_parser import telegram_specifications

        dsmr_versions = {
            '4': (SERIAL_SETTINGS_V4, telegram_specifications.V4),
            '2.2': (SERIAL_SETTINGS_V2_2, telegram_specifications.V2_2),
        }

        device = config[CONF_DEVICE]
        dsmr_version = config[CONF_DSMR_VERSION]

        self.dsmr_parser = SerialReader(
            device=device,
            serial_settings=dsmr_versions[dsmr_version][0],
            telegram_specification=dsmr_versions[dsmr_version][1],
        )

        self.hass = hass
        self.devices = devices
        self._telegram = {}

    @asyncio.coroutine
    def async_update(self):
        """Wait for DSMR telegram to be received and parsed."""

        _LOGGER.info('retrieving DSMR telegram')
        try:
            self._telegram = self.read_telegram()
        except dsmr_parser.exceptions.ParseError:
            _LOGGER.error('parse error, correct dsmr_version specified?')
        except:
            _LOGGER.exception('unexpected errur during telegram retrieval')

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def read_telegram(self):
        """Read telegram."""
        return next(self.dsmr_parser.read())

    @property
    def telegram(self):
        """Return latest received telegram."""
        return self._telegram


class DSMREntity(Entity):
    """Entity reading values from DSMR telegram."""

    def __init__(self, name, obis, interface):
        """"Initialize entity."""
        self._name = name
        self._obis = obis
        self._interface = interface

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return getattr(self._interface.telegram.get(self._obis, {}),
                       'value', None)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return getattr(self._interface.telegram.get(self._obis, {}),
                       'unit', None)


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
