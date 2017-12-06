"""
Support for Telldus Live.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/tellduslive/
"""
from datetime import datetime, timedelta
import logging

from homeassistant.const import (
    ATTR_BATTERY_LEVEL, DEVICE_DEFAULT_NAME,
    CONF_TOKEN, CONF_HOST,
    EVENT_HOMEASSISTANT_START)
from homeassistant.helpers import discovery
from homeassistant.components.discovery import SERVICE_TELLDUSLIVE
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_point_in_utc_time
from homeassistant.util.dt import utcnow
from homeassistant.util.json import load_json, save_json
import voluptuous as vol

APPLICATION_NAME = 'Home Assistant'

DOMAIN = 'tellduslive'

REQUIREMENTS = ['tellduslive==0.10.4']

_LOGGER = logging.getLogger(__name__)

TELLLDUS_CONFIG_FILE = 'tellduslive.conf'
KEY_CONFIG = 'tellduslive_config'

CONF_TOKEN_SECRET = 'token_secret'
CONF_UPDATE_INTERVAL = 'update_interval'

PUBLIC_KEY = 'THUPUNECH5YEQA3RE6UYUPRUZ2DUGUGA'
NOT_SO_PRIVATE_KEY = 'PHES7U2RADREWAFEBUSTUBAWRASWUTUS'

MIN_UPDATE_INTERVAL = timedelta(seconds=5)
DEFAULT_UPDATE_INTERVAL = timedelta(minutes=1)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): (
            vol.All(cv.time_period, vol.Clamp(min=MIN_UPDATE_INTERVAL)))
    }),
}, extra=vol.ALLOW_EXTRA)


ATTR_LAST_UPDATED = 'time_last_updated'

CONFIG_INSTRUCTIONS = """
To link your TelldusLive account:

1. Click the link below

2. Login to Telldus Live

3. Authorize {app_name}.

4. Click the Confirm button.

[Link TelldusLive account]({auth_url})
"""


def setup(hass, config, session=None):
    """Set up the Telldus Live component."""
    from tellduslive import Session, supports_local_api
    config_filename = hass.config.path(TELLLDUS_CONFIG_FILE)
    conf = load_json(config_filename)

    def request_configuration(host=None):
        """Request TelldusLive authorization."""
        configurator = hass.components.configurator
        hass.data.setdefault(KEY_CONFIG, {})
        data_key = host or DOMAIN

        # Configuration already in progress
        if hass.data[KEY_CONFIG].get(data_key):
            return

        _LOGGER.info('Configuring TelldusLive %s',
                     'local client: {}'.format(host) if host else
                     'cloud service')

        session = Session(public_key=PUBLIC_KEY,
                          private_key=NOT_SO_PRIVATE_KEY,
                          host=host,
                          application=APPLICATION_NAME)

        auth_url = session.authorize_url
        if not auth_url:
            _LOGGER.warning('Failed to retrieve authorization URL')
            return

        _LOGGER.debug('Got authorization URL %s', auth_url)

        def configuration_callback(callback_data):
            """Handle the submitted configuration."""
            session.authorize()
            res = setup(hass, config, session)
            if not res:
                configurator.notify_errors(
                    hass.data[KEY_CONFIG].get(data_key),
                    'Unable to connect.')
                return

            conf.update(
                {host: {CONF_HOST: host,
                        CONF_TOKEN: session.access_token}} if host else
                {DOMAIN: {CONF_TOKEN: session.access_token,
                          CONF_TOKEN_SECRET: session.access_token_secret}})
            save_json(config_filename, conf)
            # Close all open configurators: for now, we only support one
            # tellstick device, and configuration via either cloud service
            # or via local API, not both at the same time
            for instance in hass.data[KEY_CONFIG].values():
                configurator.request_done(instance)

        hass.data[KEY_CONFIG][data_key] = \
            configurator.request_config(
                'TelldusLive ({})'.format(
                    'LocalAPI' if host
                    else 'Cloud service'),
                configuration_callback,
                description=CONFIG_INSTRUCTIONS.format(
                    app_name=APPLICATION_NAME,
                    auth_url=auth_url),
                submit_caption='Confirm',
                entity_picture='/static/images/logo_tellduslive.png',
            )

    def tellstick_discovered(service, info):
        """Run when a Tellstick is discovered."""
        _LOGGER.info('Discovered tellstick device')

        if DOMAIN in hass.data:
            _LOGGER.debug('Tellstick already configured')
            return

        host, device = info[:2]

        if not supports_local_api(device):
            _LOGGER.debug('Tellstick does not support local API')
            # Configure the cloud service
            hass.async_add_job(request_configuration)
            return

        _LOGGER.debug('Tellstick does support local API')

        # Ignore any known devices
        if conf and host in conf:
            _LOGGER.debug('Discovered already known device: %s', host)
            return

        # Offer configuration of both live and local API
        request_configuration()
        request_configuration(host)

    discovery.listen(hass, SERVICE_TELLDUSLIVE, tellstick_discovered)

    if session:
        _LOGGER.debug('Continuing setup configured by configurator')
    elif conf and CONF_HOST in next(iter(conf.values())):
        #  For now, only one local device is supported
        _LOGGER.debug('Using Local API pre-configured by configurator')
        session = Session(**next(iter(conf.values())))
    elif DOMAIN in conf:
        _LOGGER.debug('Using TelldusLive cloud service '
                      'pre-configured by configurator')
        session = Session(PUBLIC_KEY, NOT_SO_PRIVATE_KEY,
                          application=APPLICATION_NAME, **conf[DOMAIN])
    elif config.get(DOMAIN):
        _LOGGER.info('Found entry in configuration.yaml. '
                     'Requesting TelldusLive cloud service configuration')
        request_configuration()

        if CONF_HOST in config.get(DOMAIN, {}):
            _LOGGER.info('Found TelldusLive host entry in configuration.yaml. '
                         'Requesting Telldus Local API configuration')
            request_configuration(config.get(DOMAIN).get(CONF_HOST))

        return True
    else:
        _LOGGER.info('Tellstick discovered, awaiting discovery callback')
        return True

    if not session.is_authorized:
        _LOGGER.error(
            'Authentication Error')
        return False

    client = TelldusLiveClient(hass, config, session)

    hass.data[DOMAIN] = client

    if session:
        client.update()
    else:
        hass.bus.listen(EVENT_HOMEASSISTANT_START, client.update)

    return True


class TelldusLiveClient(object):
    """Get the latest data and update the states."""

    def __init__(self, hass, config, session):
        """Initialize the Tellus data object."""
        self.entities = []

        self._hass = hass
        self._config = config

        self._interval = config.get(DOMAIN, {}).get(
            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        _LOGGER.debug('Update interval %s', self._interval)
        self._client = session

    def update(self, *args):
        """Periodically poll the servers for current state."""
        _LOGGER.debug('Updating')
        try:
            self._sync()
        finally:
            track_point_in_utc_time(
                self._hass, self.update, utcnow() + self._interval)

    def _sync(self):
        """Update local list of devices."""
        if not self._client.update():
            _LOGGER.warning('Failed request')

        def identify_device(device):
            """Find out what type of HA component to create."""
            from tellduslive import (DIM, UP, TURNON)
            if device.methods & DIM:
                return 'light'
            elif device.methods & UP:
                return 'cover'
            elif device.methods & TURNON:
                return 'switch'
            elif device.methods == 0:
                return 'binary_sensor'
            _LOGGER.warning(
                "Unidentified device type (methods: %d)", device.methods)
            return 'switch'

        def discover(device_id, component):
            """Discover the component."""
            discovery.load_platform(
                self._hass, component, DOMAIN, [device_id], self._config)

        known_ids = {entity.device_id for entity in self.entities}
        for device in self._client.devices:
            if device.device_id in known_ids:
                continue
            if device.is_sensor:
                for item in device.items:
                    discover((device.device_id, item.name, item.scale),
                             'sensor')
            else:
                discover(device.device_id,
                         identify_device(device))

        for entity in self.entities:
            entity.changed()

    def device(self, device_id):
        """Return device representation."""
        return self._client.device(device_id)

    def is_available(self, device_id):
        """Return device availability."""
        return device_id in self._client.device_ids


class TelldusLiveEntity(Entity):
    """Base class for all Telldus Live entities."""

    def __init__(self, hass, device_id):
        """Initialize the entity."""
        self._id = device_id
        self._client = hass.data[DOMAIN]
        self._client.entities.append(self)
        self._name = self.device.name
        _LOGGER.debug('Created device %s', self)

    def changed(self):
        """Return the property of the device might have changed."""
        if self.device.name:
            self._name = self.device.name
        self.schedule_update_ha_state()

    @property
    def device_id(self):
        """Return the id of the device."""
        return self._id

    @property
    def device(self):
        """Return the representation of the device."""
        return self._client.device(self.device_id)

    @property
    def _state(self):
        """Return the state of the device."""
        return self.device.state

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def assumed_state(self):
        """Return true if unable to access real state of entity."""
        return True

    @property
    def name(self):
        """Return name of device."""
        return self._name or DEVICE_DEFAULT_NAME

    @property
    def available(self):
        """Return true if device is not offline."""
        return self._client.is_available(self.device_id)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {}
        if self._battery_level:
            attrs[ATTR_BATTERY_LEVEL] = self._battery_level
        if self._last_updated:
            attrs[ATTR_LAST_UPDATED] = self._last_updated
        return attrs

    @property
    def _battery_level(self):
        """Return the battery level of a device."""
        from tellduslive import (BATTERY_LOW,
                                 BATTERY_UNKNOWN,
                                 BATTERY_OK)
        if self.device.battery == BATTERY_LOW:
            return 1
        elif self.device.battery == BATTERY_UNKNOWN:
            return None
        elif self.device.battery == BATTERY_OK:
            return 100
        else:
            return self.device.battery  # Percentage

    @property
    def _last_updated(self):
        """Return the last update of a device."""
        return str(datetime.fromtimestamp(self.device.lastUpdated)) \
            if self.device.lastUpdated else None
