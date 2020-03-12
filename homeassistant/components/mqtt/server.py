"""Support for a local MQTT broker."""
import logging
import tempfile

import voluptuous as vol

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
import homeassistant.helpers.config_validation as cv

from .const import PROTOCOL_311

_LOGGER = logging.getLogger(__name__)

# None allows custom config to be created through generate_config
HBMQTT_CONFIG_SCHEMA = vol.Any(
    None,
    vol.Schema(
        {
            vol.Optional("auth"): vol.Schema(
                {vol.Optional("password-file"): cv.isfile}, extra=vol.ALLOW_EXTRA
            ),
            vol.Optional("listeners"): vol.Schema(
                {vol.Required("default"): vol.Schema(dict), str: vol.Schema(dict)}
            ),
        },
        extra=vol.ALLOW_EXTRA,
    ),
)


async def async_start(hass, password, server_config):
    """Initialize MQTT Server.

    This method is a coroutine.
    """
    # pylint: disable=import-outside-toplevel
    from hbmqtt.broker import Broker, BrokerException

    passwd = tempfile.NamedTemporaryFile()

    gen_server_config, client_config = generate_config(hass, passwd, password)

    try:
        if server_config is None:
            server_config = gen_server_config

        broker = Broker(server_config, hass.loop)
        await broker.start()
    except BrokerException:
        _LOGGER.exception("Error initializing MQTT server")
        return False, None
    finally:
        passwd.close()

    async def async_shutdown_mqtt_server(event):
        """Shut down the MQTT server."""
        await broker.shutdown()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_shutdown_mqtt_server)

    return True, client_config


def generate_config(hass, passwd, password):
    """Generate a configuration based on current Home Assistant instance."""
    # pylint: disable=import-outside-toplevel
    from passlib.apps import custom_app_context

    config = {
        "listeners": {
            "default": {
                "max-connections": 50000,
                "bind": "0.0.0.0:1883",
                "type": "tcp",
            },
            "ws-1": {"bind": "0.0.0.0:8080", "type": "ws"},
        },
        "auth": {"allow-anonymous": password is None},
        "plugins": ["auth_anonymous"],
        "topic-check": {"enabled": True, "plugins": ["topic_taboo"]},
    }

    if password:
        username = "homeassistant"

        # Encrypt with what hbmqtt uses to verify
        passwd.write(
            f"homeassistant:{custom_app_context.encrypt(password)}\n".encode("utf-8")
        )
        passwd.flush()

        config["auth"]["password-file"] = passwd.name
        config["plugins"].append("auth_file")
    else:
        username = None

    client_config = ("localhost", 1883, username, password, None, PROTOCOL_311)

    return config, client_config
