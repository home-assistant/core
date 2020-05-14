"""Asuswrt status sensors."""
import logging

from aioasuswrt.asuswrt import AsusWrt

from homeassistant.const import DATA_GIGABYTES, DATA_RATE_MEGABITS_PER_SECOND
from homeassistant.helpers.entity import Entity

from . import DATA_ASUSWRT

_LOGGER = logging.getLogger(__name__)

UPLOAD_ICON = "mdi:upload-network"
DOWNLOAD_ICON = "mdi:download-network"


async def async_setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the asuswrt sensors."""
    if discovery_info is None:
        return

    api = hass.data[DATA_ASUSWRT]

    devices = []

    if "devices" in discovery_info:
        devices.append(AsuswrtDevicesSensor(api))
    if "download" in discovery_info:
        devices.append(AsuswrtTotalRXSensor(api))
    if "upload" in discovery_info:
        devices.append(AsuswrtTotalTXSensor(api))
    if "download_speed" in discovery_info:
        devices.append(AsuswrtRXSensor(api))
    if "upload_speed" in discovery_info:
        devices.append(AsuswrtTXSensor(api))

    add_entities(devices)


class AsuswrtSensor(Entity):
    """Representation of a asuswrt sensor."""

    _name = "generic"

    def __init__(self, api: AsusWrt):
        """Initialize the sensor."""
        self._api = api
        self._state = None
        self._devices = None
        self._rates = None
        self._speed = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    async def async_update(self):
        """Fetch status from asuswrt."""
        self._devices = await self._api.async_get_connected_devices()
        self._rates = await self._api.async_get_bytes_total()
        self._speed = await self._api.async_get_current_transfer_rates()


class AsuswrtDevicesSensor(AsuswrtSensor):
    """Representation of a asuswrt download speed sensor."""

    _name = "Asuswrt Devices Connected"

    async def async_update(self):
        """Fetch new state data for the sensor."""
        await super().async_update()
        if self._devices:
            self._state = len(self._devices)


class AsuswrtRXSensor(AsuswrtSensor):
    """Representation of a asuswrt download speed sensor."""

    _name = "Asuswrt Download Speed"
    _unit = DATA_RATE_MEGABITS_PER_SECOND

    @property
    def icon(self):
        """Return the icon."""
        return DOWNLOAD_ICON

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    async def async_update(self):
        """Fetch new state data for the sensor."""
        await super().async_update()
        if self._speed:
            self._state = round(self._speed[0] / 125000, 2)


class AsuswrtTXSensor(AsuswrtSensor):
    """Representation of a asuswrt upload speed sensor."""

    _name = "Asuswrt Upload Speed"
    _unit = DATA_RATE_MEGABITS_PER_SECOND

    @property
    def icon(self):
        """Return the icon."""
        return UPLOAD_ICON

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    async def async_update(self):
        """Fetch new state data for the sensor."""
        await super().async_update()
        if self._speed:
            self._state = round(self._speed[1] / 125000, 2)


class AsuswrtTotalRXSensor(AsuswrtSensor):
    """Representation of a asuswrt total download sensor."""

    _name = "Asuswrt Download"
    _unit = DATA_GIGABYTES

    @property
    def icon(self):
        """Return the icon."""
        return DOWNLOAD_ICON

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    async def async_update(self):
        """Fetch new state data for the sensor."""
        await super().async_update()
        if self._rates:
            self._state = round(self._rates[0] / 1000000000, 1)


class AsuswrtTotalTXSensor(AsuswrtSensor):
    """Representation of a asuswrt total upload sensor."""

    _name = "Asuswrt Upload"
    _unit = DATA_GIGABYTES

    @property
    def icon(self):
        """Return the icon."""
        return UPLOAD_ICON

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    async def async_update(self):
        """Fetch new state data for the sensor."""
        await super().async_update()
        if self._rates:
            self._state = round(self._rates[1] / 1000000000, 1)
