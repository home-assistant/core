"""Support for Google Home Bluetooth tacker."""
from datetime import timedelta
import logging

from homeassistant.components.device_tracker import DeviceScanner
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import slugify

from . import CLIENT, DOMAIN as GOOGLEHOME_DOMAIN, NAME

_LOGGER = logging.getLogger(__name__)

DEFAULT_SCAN_INTERVAL = timedelta(seconds=10)


async def async_setup_scanner(hass, config, async_see, discovery_info=None):
    """Validate the configuration and return a Google Home scanner."""
    if discovery_info is None:
        _LOGGER.warning(
            "To use this you need to configure the 'googlehome' component")
        return False
    scanner = GoogleHomeDeviceScanner(hass, hass.data[CLIENT],
                                      discovery_info, async_see)
    return await scanner.async_init()


class GoogleHomeDeviceScanner(DeviceScanner):
    """This class queries a Google Home unit."""

    def __init__(self, hass, client, config, async_see):
        """Initialize the scanner."""
        self.async_see = async_see
        self.hass = hass
        self.rssi = config['rssi_threshold']
        self.device_types = config['device_types']
        self.host = config['host']
        self.client = client

    async def async_init(self):
        """Further initialize connection to Google Home."""
        await self.client.update_info(self.host)
        data = self.hass.data[GOOGLEHOME_DOMAIN][self.host]
        info = data.get('info', {})
        connected = bool(info)
        if connected:
            await self.async_update()
            async_track_time_interval(self.hass,
                                      self.async_update,
                                      DEFAULT_SCAN_INTERVAL)
        return connected

    async def async_update(self, now=None):
        """Ensure the information from Google Home is up to date."""
        _LOGGER.debug('Checking Devices on %s', self.host)
        await self.client.update_bluetooth(self.host)
        data = self.hass.data[GOOGLEHOME_DOMAIN][self.host]
        info = data.get('info')
        bluetooth = data.get('bluetooth')
        if info is None or bluetooth is None:
            return
        google_home_name = info.get('name', NAME)

        for device in bluetooth:
            if (device['device_type'] not in
                    self.device_types or device['rssi'] < self.rssi):
                continue

            name = "{} {}".format(self.host, device['mac_address'])

            attributes = {}
            attributes['btle_mac_address'] = device['mac_address']
            attributes['ghname'] = google_home_name
            attributes['rssi'] = device['rssi']
            attributes['source_type'] = 'bluetooth'
            if device['name']:
                attributes['name'] = device['name']

            await self.async_see(dev_id=slugify(name),
                                 attributes=attributes)
