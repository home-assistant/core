"""
Remote control support for the LG Netcast TV.


For more details about this platform, please refer to the documentation
https://home-assistant.io/components/remove.lg_netcast/
"""
import time
from requests import RequestException
import voluptuous as vol
from homeassistant.components.remote import (RemoteDevice, PLATFORM_SCHEMA,
                                             ATTR_NUM_REPEATS, ATTR_DELAY_SECS,
                                             DEFAULT_DELAY_SECS)
from homeassistant.const import (CONF_HOST, CONF_NAME,
                                 CONF_ACCESS_TOKEN, DEVICE_DEFAULT_NAME,
                                 STATE_OFF)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pylgnetcast-homeassistant==0.2.0.dev0']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEVICE_DEFAULT_NAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_ACCESS_TOKEN):
        vol.All(cv.string, vol.Length(max=6)),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the LG Netcast remotes."""

    from pylgnetcast import LgNetCastClient
    host = config.get(CONF_HOST)
    access_token = config.get(CONF_ACCESS_TOKEN)
    name = config.get(CONF_NAME)

    client = LgNetCastClient(host, access_token)

    add_devices([LGNetcastRemote(client, name)], True)


class LGNetcastRemote(RemoteDevice):
    """Representation of a LG Netcast remote."""

    def __init__(self, client, name):
        """Initialize the LG Netcast Remote."""
        self._client = client
        self._name = name
        self._state = False
        self._icon = None
        self._last_command_sent = None

    @property
    def should_poll(self):
        """No polling needed for a LG Netcast remote."""
        return False

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use for device if any."""
        return self._icon

    @property
    def is_on(self):
        """Return true if remote is on."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return device state attributes."""
        if self._last_command_sent is not None:
            return {'last_command_sent': self._last_command_sent}

    def turn_on(self, **kwargs):
        """Turn the remote on."""
        self._state = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the remote off."""
        self._state = False
        self.send_command(1)
        self.schedule_update_ha_state()

    def send_command(self, commands, **kwargs):
        """Send a command to a device."""
        from pylgnetcast import LgNetCastError, LG_COMMAND
        num_repeats = kwargs.get(ATTR_NUM_REPEATS)

        delay = kwargs.get(ATTR_DELAY_SECS, DEFAULT_DELAY_SECS)
        for _ in range(num_repeats):
            for command in commands:
                try:
                    with self._client as client:
                        if isinstance(command, str):
                            command = getattr(LG_COMMAND, command.upper())
                        client.send_command(command)
                except (LgNetCastError, RequestException):
                    self._state = STATE_OFF
            time.sleep(delay)
            self._last_command_sent = command
        self.schedule_update_ha_state()
