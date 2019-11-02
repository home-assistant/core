"""Integration with the Particle Cloud."""
import logging

import voluptuous as vol

from homeassistant.const import CONF_ACCESS_TOKEN, STATE_ON, STATE_UNAVAILABLE
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import ENTITY_SERVICE_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent

DOMAIN = "particle"

_LOGGER = logging.getLogger(DOMAIN)
CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Required(CONF_ACCESS_TOKEN): cv.string})},
    extra=vol.ALLOW_EXTRA,
)

ATTR_ARGS = "args"
ATTR_FUNCTION = "function"

FUNCTION_CALL_SCHEMA = ENTITY_SERVICE_SCHEMA.extend(
    {
        vol.Required(ATTR_FUNCTION): cv.string,
        vol.Optional(ATTR_ARGS): vol.All(
            cv.ensure_list, vol.Length(min=1), [cv.string]
        ),
    }
)


async def async_setup(hass, config):
    """Initialize our component while Home Assistant loads."""
    if DOMAIN not in config:
        return True

    from pyparticleio.ParticleCloud import ParticleCloud

    access_token = config[DOMAIN][CONF_ACCESS_TOKEN]

    try:
        particle = hass.data[DOMAIN] = ParticleCloud(access_token)
    except Exception as ex:
        _LOGGER.error("Unable to connect to Particle Cloud: %s", str(ex))
        return False

    component = EntityComponent(_LOGGER, DOMAIN, hass)

    devices = {}
    device_list = []

    for name, info in particle.devices.items():
        entity_id = f"{DOMAIN}.{name.lower()}"

        device = ParticleDevice(name, info)
        devices[entity_id] = device
        device_list.append(device)

    if not device_list:
        return False

    component.async_register_entity_service(
        "call", FUNCTION_CALL_SCHEMA, ParticleDevice.call
    )

    await component.async_add_entities(device_list)
    return True


class ParticleDevice(Entity):
    """ParticleDevice represents a single device within the Particle Cloud."""

    def __init__(self, name, info):
        """Initialize the Device from its initial state."""
        self._name = name
        self._info = info
        self._attributes = {}

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def icon(self):
        """Return an icon representing the device."""
        return "mdi:star-four-points"

    @property
    def available(self):
        """Return true if the device is connected, false otherwise."""
        return self._info.connected

    @property
    def state(self):
        """Return a high-level state for the device."""
        if self._info.connected:
            return STATE_ON
        else:
            return STATE_UNAVAILABLE

    def call(self, service):
        """Call a specified Cloud Function available on the device."""
        function = service.data.get(ATTR_FUNCTION)
        args = service.data.get(ATTR_ARGS, [])

        source = f"self._info.{function}(*args)"

        return eval(source, {"self": self, "args": args})

    @property
    def device_state_attributes(self):
        """Return all Cloud Variables published from the device."""
        return self._attributes

    def update(self):
        """Get the latest data from the Particle Cloud for this device."""
        if self._info.variables is not None:
            for name, _ in self._info.variables.items():
                source = f"self._info.{name}"
                try:
                    self._attributes[name] = eval(source, {"self": self})
                except Exception as ex:
                    _LOGGER.error("Unable to update from Particle Cloud: %s", str(ex))
                    self._attributes[name] = None
