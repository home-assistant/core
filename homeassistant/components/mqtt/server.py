"""
Support for a local MQTT broker.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/mqtt/#use-the-embedded-broker
"""
import asyncio
import logging
import tempfile

import voluptuous as vol

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['hbmqtt==0.9.4']

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['http']

# None allows custom config to be created through generate_config
HBMQTT_CONFIG_SCHEMA = vol.Any(None, vol.Schema({
    vol.Optional('auth'): vol.Schema({
        vol.Optional('password-file'): cv.isfile,
    }, extra=vol.ALLOW_EXTRA),
    vol.Optional('listeners'): vol.Schema({
        vol.Required('default'): vol.Schema(dict),
        str: vol.Schema(dict)
    })
}, extra=vol.ALLOW_EXTRA))


@asyncio.coroutine
def async_start(hass, password, server_config):
    """Initialize MQTT Server.

    This method is a coroutine.
    """
    from hbmqtt.broker import Broker, BrokerException

    passwd = tempfile.NamedTemporaryFile()
    try:
        if server_config is None:
            server_config, client_config = generate_config(
                hass, passwd, password)
        else:
            client_config = None

        broker = Broker(server_config, hass.loop)
        yield from broker.start()
    except BrokerException:
        _LOGGER.exception("Error initializing MQTT server")
        return False, None
    finally:
        passwd.close()

    @asyncio.coroutine
    def async_shutdown_mqtt_server(event):
        """Shut down the MQTT server."""
        yield from broker.shutdown()

    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, async_shutdown_mqtt_server)

    return True, client_config


def generate_config(hass, passwd, password):
    """Generate a configuration based on current Home Assistant instance."""
    from . import PROTOCOL_311

    config = {
        'listeners': {
            'default': {
                'max-connections': 50000,
                'bind': '0.0.0.0:1883',
                'type': 'tcp',
            },
            'ws-1': {
                'bind': '0.0.0.0:8080',
                'type': 'ws',
            },
        },
        'auth': {
            'allow-anonymous': password is None
        },
        'plugins': ['auth_anonymous'],
        'topic-check': {
            'enabled': True,
            'plugins': ['topic_taboo'],
        },
    }

    if password:
        username = 'homeassistant'

        # Encrypt with what hbmqtt uses to verify
        from passlib.apps import custom_app_context

        passwd.write(
            'homeassistant:{}\n'.format(
                custom_app_context.encrypt(password)).encode('utf-8'))
        passwd.flush()

        config['auth']['password-file'] = passwd.name
        config['plugins'].append('auth_file')
    else:
        username = None

    client_config = ('localhost', 1883, username, password, None, PROTOCOL_311)

    return config, client_config
