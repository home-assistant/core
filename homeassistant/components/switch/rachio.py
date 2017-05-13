import logging
import voluptuous as vol
from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import homeassistant.util as util
from homeassistant.components.switch import SwitchDevice, PLATFORM_SCHEMA
from homeassistant.const import CONF_ACCESS_TOKEN

REQUIREMENTS = ['https://github.com/Klikini/rachiopy'
                '/archive/edf666de8ef3f9596ddc8d3a989e8c4b829a4319.zip'
                '#rachiopy==0.1.1']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'switch'

DATA_RACHIO = 'rachio'

CONF_manual_run_mins = 'manual_run_mins'
manual_run_mins = 60

STATUS_ONLINE = 'ONLINE'

MIN_UPDATE_INTERVAL = timedelta(minutes=5)
MIN_FORCED_UPDATE_INTERVAL = timedelta(seconds=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ACCESS_TOKEN): cv.string
})

_IRO = None


# Set up the component
# noinspection PyUnusedLocal
def setup_platform(hass, config, add_devices, discovery_info=None):
    global _IRO
    global manual_run_mins

    # Get options
    manual_run_mins = config.get(CONF_manual_run_mins) or manual_run_mins
    _LOGGER.debug("Rachio run time is " + str(manual_run_mins) + " min")

    # Get access token
    _LOGGER.debug("Getting Rachio access token...")
    access_token = config.get(CONF_ACCESS_TOKEN)
    if not access_token:
        _LOGGER.error("Rachio API access token must be set "
                      "in the configuration")
        return False

    # Configure API
    _LOGGER.debug("Configuring Rachio API...")
    from rachiopy import Rachio
    r = Rachio(access_token)
    person = _get_person(r)

    # Get and persist devices
    devices = _list_devices(r)
    if len(devices) == 0:
        _LOGGER.error("No Rachio devices found in account " +
                      person['username'])
        return False
    else:
        _IRO = devices[0]

        if len(devices) > 1:
            _LOGGER.warning("Multiple Rachio devices found in account, "
                            "using " + _IRO.device_id)
        else:
            _LOGGER.info("Found Rachio device")

    _IRO.update()
    add_devices(_IRO.list_zones())
    return True


# Pull the account info of the person whose access token was provided
def _get_person(r):
    person_id = r.person.getInfo()[1]['id']
    return r.person.get(person_id)[1]


# Pull a list of devices on the account
def _list_devices(r):
    return [RachioIro(r, d['id']) for d in _get_person(r)['devices']]


# Represents one Rachio Iro
class RachioIro(object):
    def __init__(self, r, device_id):
        self.r = r
        self._device_id = device_id
        self._device = None
        self._running = None
        self._zones = None

    def __str__(self):
        return "Rachio Iro " + self.serial_number

    @property
    def device_id(self):
        return self._device['id']

    @property
    def status(self):
        return self._device['status']

    @property
    def serial_number(self):
        return self._device['serialNumber']

    @property
    def is_paused(self):
        return self._device['paused']

    @property
    def is_on(self):
        return self._device['on']

    @property
    def current_schedule(self):
        return self._running

    def list_zones(self, include_disabled=False):
        if not self._zones:
            self._zones = [RachioZone(self.r, self, zone['id'])
                           for zone in self._device['zones']]

        if include_disabled:
            return self._zones
        else:
            self.update(propagate=True, no_throttle=True)
            return [z for z in self._zones if z.is_enabled]

    # Pull updated device info from the Rachio API
    @util.Throttle(MIN_UPDATE_INTERVAL, MIN_FORCED_UPDATE_INTERVAL)
    def update(self, propagate=True):
        self._device = self.r.device.get(self._device_id)[1]
        self._running = self.r.device.getCurrentSchedule(self._device_id)[1]

        # Possibly update all zones
        if propagate:
            for zone in self.list_zones(include_disabled=True):
                zone.update(propagate=False)

        _LOGGER.debug("Updated " + str(self))


# Represents one zone of sprinklers connected to the Rachio Iro
class RachioZone(SwitchDevice):
    def __init__(self, r, device, zone_id):
        self.r = r
        self._device = device
        self._zone_id = zone_id
        self._zone = None

    def __str__(self):
        return "Rachio Zone " + self.name

    @property
    def zone_id(self):
        return self._zone['id']

    @property
    def unique_id(self):
        return '{iro}-{zone}'.format(
            iro=self._device.device_id,
            zone=self.zone_id)

    @property
    def number(self):
        return self._zone['zoneNumber']

    @property
    def name(self):
        return self._zone['name'] or "Zone " + self.number

    @property
    def is_enabled(self):
        return self._zone['enabled']

    # TODO: fix this always returning false
    @property
    def is_on(self):
        self._device.update(propagate=False)
        schedule = self._device.current_schedule
        if 'zoneId' in schedule:
            # Something is running, is it this zone?
            return self.zone_id == schedule['zoneId']
        else:
            # Nothing is running
            return False

    # Pull updated zone info from the Rachio API
    @util.Throttle(MIN_UPDATE_INTERVAL, MIN_FORCED_UPDATE_INTERVAL)
    def update(self, propagate=True):
        self._zone = self.r.zone.get(self._zone_id)[1]

        # Possibly update device
        if propagate:
            self._device.update()

        _LOGGER.debug("Updated " + str(self))

    # Start the zone and return the response headers
    def turn_on(self, seconds=None):
        seconds = seconds or (manual_run_mins * 60)

        # Stop other zones first
        self.turn_off()

        _LOGGER.info("Watering {} for {} sec".format(self.name, seconds))
        headers = self.r.zone.start(self.zone_id, seconds)[0]
        self.update(no_throttle=True)
        return headers

    # Stop all zones and return the response headers
    def turn_off(self):
        _LOGGER.info("Stopping watering of all zones")
        headers = self.r.device.stopWater(self._device.device_id)[0]
        self.update(no_throttle=True)
        return headers

