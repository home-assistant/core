"""
Support for OWFS sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.owfs/
"""

from datetime import timedelta

from homeassistant.components.owfs import (OWFSDevice, init_devices,
                                           DEVICE_SCHEMA)
from homeassistant.components.sensor import PLATFORM_SCHEMA

from trio_owfs.event import DeviceValue

DEPENDENCIES = ['owfs']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(DEVICE_SCHEMA.schema)

SCAN_INTERVAL = timedelta(
    minutes=5)  # default; don't do it too often, may be expensive


async def async_setup_platform(hass,
                               config,
                               async_add_entities,
                               discovery_info=None):
    """Set up sensor(s) for OWFS platform."""

    await init_devices(hass, 'sensor', config, discovery_info,
                       async_add_entities, CLASSES)


class TemperatureSensor(OWFSDevice):
    """Representation of an OWFS temperature sensor."""

    _attr = "temperature"
    temperature = None

    async def _init(self, without_config: bool):
        """Async part of device initialization."""
        await super()._init(without_config)
        if without_config:
            await self.dev.set_polling_interval("temperature", 30)

    async def process_event(self, event):
        if isinstance(event, DeviceValue) and \
                event.attribute in {'temperature', 'latesttemp'}:
            self.temperature = event.value

        await super().process_event(event)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.temperature

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return "°C"

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return None  # XXX


CLASSES = {
    0x10: TemperatureSensor,
}
