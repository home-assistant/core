"""
Remote control support for the LG Netcast TV.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/remote.lg_netcast/
"""
import asyncio
from datetime import timedelta
from requests import RequestException
import voluptuous as vol

from homeassistant import util
from homeassistant.components.remote import (RemoteDevice, PLATFORM_SCHEMA,
                                             ATTR_NUM_REPEATS, ATTR_DELAY_SECS,
                                             DEFAULT_DELAY_SECS)
from homeassistant.const import (CONF_HOST, CONF_NAME,
                                 CONF_ACCESS_TOKEN,
                                 STATE_OFF, STATE_ON)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pylgnetcast-homeassistant==0.2.0.dev0']

MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(seconds=1)
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

DEFAULT_NAME = 'LG TV Remote'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_ACCESS_TOKEN):
        vol.All(cv.string, vol.Length(max=6)),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the LG Netcast remotes."""

    from pylgnetcast import LgNetCastClient
    host = config[CONF_HOST]
    access_token = config.get(CONF_ACCESS_TOKEN)
    name = config[CONF_NAME]

    client = LgNetCastClient(host, access_token)

    add_entities([LGNetcastRemote(client, name)], True)


class LGNetcastRemote(RemoteDevice):
    """Representation of a LG Netcast remote."""

    def __init__(self, client, name):
        """Initialize the LG Netcast Remote."""
        self._client = client
        self._name = name
        self._state = False
        self._last_command_sent = None

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update(self):
        """Retrieve the latest data from the LG TV."""
        from pylgnetcast import LgNetCastError, LG_QUERY
        try:
            with self._client as client:
                client.query_data(LG_QUERY.VOLUME_INFO)
                self._state = STATE_ON
        except (LgNetCastError, RequestException):
            self._state = STATE_OFF

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def is_on(self):
        """Return true if remote is on."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return device state attributes."""
        if self._last_command_sent is not None:
            return {'last_command_sent': self._last_command_sent}
        return None

    def turn_on(self, **kwargs):
        """Turn the remote on."""
        self._state = STATE_ON  # Turn on not support by LG Netcast TV
        self.schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn the remote off."""
        await self.async_send_command(1)

    async def async_send_command(self, command, **kwargs):
        """Send a command to a device."""
        from pylgnetcast import LgNetCastError, LG_COMMAND
        num_repeats = kwargs.get(ATTR_NUM_REPEATS)

        delay = kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS)
        for _ in range(num_repeats):
            cmdline = ''
            for cmdline in command:
                try:
                    with self._client as client:
                        if isinstance(cmdline, str):
                            cmdline = getattr(LG_COMMAND, cmdline.upper())
                        client.send_command(cmdline)
                except (LgNetCastError, RequestException):
                    self._state = STATE_OFF
            await asyncio.sleep(delay)
            self._last_command_sent = cmdline
        self.schedule_update_ha_state()
