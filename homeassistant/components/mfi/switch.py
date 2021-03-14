"""Support for Ubiquiti mFi switches."""
import logging

from mficlient.client import FailedToLogin, MFiClient
import requests
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_SSL = True
DEFAULT_VERIFY_SSL = True

SWITCH_MODELS = ["Outlet", "Output 5v", "Output 12v", "Output 24v", "Dimmer Switch"]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PORT): cv.port,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up mFi sensors."""
    host = config.get(CONF_HOST)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    use_tls = config[CONF_SSL]
    verify_tls = config.get(CONF_VERIFY_SSL)
    default_port = 6443 if use_tls else 6080
    port = int(config.get(CONF_PORT, default_port))

    try:
        client = MFiClient(
            host, username, password, port=port, use_tls=use_tls, verify=verify_tls
        )
    except (FailedToLogin, requests.exceptions.ConnectionError) as ex:
        _LOGGER.error("Unable to connect to mFi: %s", str(ex))
        return False

    add_entities(
        MfiSwitch(port)
        for device in client.get_devices()
        for port in device.ports.values()
        if port.model in SWITCH_MODELS
    )


class MfiSwitch(SwitchEntity):
    """Representation of an mFi switch-able device."""

    def __init__(self, port):
        """Initialize the mFi device."""
        self._port = port
        self._target_state = None

    @property
    def unique_id(self):
        """Return the unique ID of the device."""
        return self._port.ident

    @property
    def name(self):
        """Return the name of the device."""
        return self._port.label

    @property
    def is_on(self):
        """Return true if the device is on."""
        return self._port.output

    def update(self):
        """Get the latest state and update the state."""
        self._port.refresh()
        if self._target_state is not None:
            self._port.data["output"] = float(self._target_state)
            self._target_state = None

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self._port.control(True)
        self._target_state = True

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self._port.control(False)
        self._target_state = False

    @property
    def current_power_w(self):
        """Return the current power usage in W."""
        return int(self._port.data.get("active_pwr", 0))

    @property
    def extra_state_attributes(self):
        """Return the state attributes for the device."""
        return {
            "volts": round(self._port.data.get("v_rms", 0), 1),
            "amps": round(self._port.data.get("i_rms", 0), 1),
        }
