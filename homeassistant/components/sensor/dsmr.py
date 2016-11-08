"""
Support for Dutch Smart Meter Requirements.

Also known as: Smartmeter or P1 port.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.dsmr/
"""

import logging
import asyncio

from homeassistant.helpers.entity import Entity
from homeassistant.const import CONF_DEVICE

DOMAIN = 'dsmr'

REQUIREMENTS = ['dsmr_parser']

DEFAULT_DEVICE = '/dev/ttyUSB0'
DEFAULT_DSMR_VERSION = '2.2'

CONF_DSMR_VERSION = 'dsmr_version'

log = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    from dsmr_parser.obis_references import (
        CURRENT_ELECTRICITY_USAGE,
        CURRENT_ELECTRICITY_DELIVERY,
        ELECTRICITY_ACTIVE_TARIFF
    )

    devices = []

    dsmr = DSMR(hass, config, devices)

    devices += [
        DSMREntity('Power Usage', CURRENT_ELECTRICITY_USAGE, dsmr),
        DSMREntity('Power Production', CURRENT_ELECTRICITY_DELIVERY, dsmr),
        DSMRTariff('Power Tariff', ELECTRICITY_ACTIVE_TARIFF, dsmr),
    ]
    yield from async_add_devices(devices, True)

    yield from dsmr.async_update()


class DSMR:
    """DSMR interface."""

    def __init__(self, hass, config, devices):
        """Setup DSMR serial interface and add device entities."""

        from dsmr_parser.serial import (
            SERIAL_SETTINGS_V2_2,
            SERIAL_SETTINGS_V4,
            SerialReader
        )
        from dsmr_parser import telegram_specifications

        dsmr_versions = {
            '2.2': (SERIAL_SETTINGS_V2_2, telegram_specifications.V2_2),
            '4': (SERIAL_SETTINGS_V4, telegram_specifications.V4),
        }

        device = config.get(CONF_DEVICE, DEFAULT_DEVICE)
        dsmr_version = config.get(CONF_DSMR_VERSION, DEFAULT_DSMR_VERSION)

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

        while True:
            if hasattr(self.dsmr_parser, 'serial_handle'):
                print(self.dsmr_parser.serial_handle.in_waiting)
            log.info('retrieving new telegram')
            self._telegram = next(self.dsmr_parser.read())
            log.info('got new telegram')
            yield from asyncio.sleep(10)

            tasks = []
            for device in self.devices:
                tasks.append(device.async_update_ha_state())

            yield from asyncio.gather(*tasks, loop=self.hass.loop)

    @property
    def telegram(self):
        """Return latest received telegram."""

        return self._telegram


class DSMREntity(Entity):
    """Entity reading values from DSMR telegram."""

    def __init__(self, name, obis, interface):
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
        """Convert 2/1 to high/low."""

        tariff = super().state
        print(type(tariff), tariff)
        if tariff == '0002':
            return 'high'
        elif tariff == '0001':
            return 'low'
        else:
            return None
