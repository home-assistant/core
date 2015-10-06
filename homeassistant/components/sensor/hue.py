"""
homeassistant.components.sensor.hue
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for Hue Tap.
"""
import logging
import socket
from urllib.parse import urlparse
from datetime import timedelta, datetime, timezone
from homeassistant import util
from homeassistant.const import CONF_HOST, DEVICE_DEFAULT_NAME
from homeassistant.helpers.entity import Entity
from homeassistant.loader import get_component

REQUIREMENTS = ['phue==0.8']
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=5)
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(milliseconds=100)

PHUE_CONFIG_FILE = "phue.conf"

_CONFIGURING = {}
_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Gets the Hue sensors. """
    try:
        # pylint: disable=unused-variable
        import phue  # noqa
    except ImportError:
        _LOGGER.exception("Error while importing dependency phue.")

        return

    if discovery_info is not None:
        host = urlparse(discovery_info[1]).hostname
    else:
        host = config.get(CONF_HOST, None)

    # Only act if we are not already configuring this host
    if host in _CONFIGURING:
        return

    setup_bridge(host, hass, add_devices_callback)


def setup_bridge(host, hass, add_devices_callback):
    """ Setup a phue bridge based on host parameter. """
    import phue

    try:
        bridge = phue.Bridge(
            host,
            config_file_path=hass.config.path(PHUE_CONFIG_FILE))
    except ConnectionRefusedError:  # Wrong host was given
        _LOGGER.exception("Error connecting to the Hue bridge at %s", host)

        return

    except phue.PhueRegistrationException:
        _LOGGER.warning("Connected to Hue at %s but not registered.", host)

        request_configuration(host, hass, add_devices_callback)

        return

    # If we came here and configuring this host, mark as done
    if host in _CONFIGURING:
        request_id = _CONFIGURING.pop(host)

        configurator = get_component('configurator')

        configurator.request_done(request_id)

    sensors = {}

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update_sensors():
        """ Updates the Hue sensor objects with latest info from the bridge. """
        try:
            api = bridge.get_api()
        except socket.error:
            # socket.error when we cannot reach Hue
            _LOGGER.exception("Cannot reach the bridge")
            return

        api_states = api.get('sensors')

        if not isinstance(api_states, dict):
            _LOGGER.error("Got unexpected result from Hue API")
            return

        new_sensors = []

        for sensor_id, info in api_states.items():
            if sensor_id == "1":
                continue
            if sensor_id not in sensors:
                sensors[sensor_id] = HueSensor(int(sensor_id), info, bridge, update_sensors)
                new_sensors.append(sensors[sensor_id])
            else:
                sensors[sensor_id].info = info

        if new_sensors:
            add_devices_callback(new_sensors)

    update_sensors()


def request_configuration(host, hass, add_devices_callback):
    """ Request configuration steps from the user. """
    configurator = get_component('configurator')

    # We got an error if this method is called while we are configuring
    if host in _CONFIGURING:
        configurator.notify_errors(
            _CONFIGURING[host], "Failed to register, please try again.")

        return

    def hue_configuration_callback(data):
        """ Actions to do when our configuration callback is called. """
        setup_bridge(host, hass, add_devices_callback)

    _CONFIGURING[host] = configurator.request_config(
        hass, "Philips Hue", hue_configuration_callback,
        description=("Press the button on the bridge to register Philips Hue "
                     "with Home Assistant."),
        description_image="/static/images/config_philips_hue.jpg",
        submit_caption="I have pressed the button"
    )


class HueSensor(Entity):
    """ Represents a Hue sensor """

    def __init__(self, light_id, info, bridge, update_sensors):
        self.light_id = light_id
        self.info = info
        self.bridge = bridge
        self.update_sensors = update_sensors

    @property
    def state(self):
        """ Returns the state of the entity. """
        return self.last_button

    @property
    def unique_id(self):
        """ Returns the id of this Hue sensor """
        return "{}.{}".format(
            self.__class__, self.info.get('uniqueid', self.name))

    @property
    def name(self):
        """ Get the mame of the Hue sensor. """
        return self.info.get('name', DEVICE_DEFAULT_NAME)

    @property
    def last_button(self):

        last_updated = datetime.strptime(self.info.get('state', {})
                                         .get('lastupdated', '1970-01-01T00:00:00'), '%Y-%m-%dT%H:%M:%S')\
            .replace(tzinfo=timezone.utc)

        seconds_passed = datetime.now(timezone.utc) - last_updated
        _LOGGER.info("Seconds since last press: "+str(seconds_passed.total_seconds()))

        if seconds_passed.total_seconds() > 6:
            return 0

        return {
            34: 1,
            16: 2,
            17: 3,
            18: 4,
            }.get(self.info.get('state', {}).get('buttonevent', 0), 0)

    def update(self):
        """ Synchronize state with bridge. """
        self.update_sensors(no_throttle=True)
