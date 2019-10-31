"""Integration with the Particle Cloud."""

DOMAIN = 'particle'

import logging
import voluptuous as vol
from homeassistant.const import (
  STATE_ON,
  STATE_UNAVAILABLE,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import ENTITY_SERVICE_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent

_LOGGER = logging.getLogger(DOMAIN)
CONFIG_SCHEMA = vol.Schema({
  DOMAIN: vol.Schema({
    vol.Required('access_token'): cv.string,
  }),
}, extra=vol.ALLOW_EXTRA)

FUNCTION_CALL_SCHEMA = ENTITY_SERVICE_SCHEMA.extend({
  vol.Required('function'): cv.string,
  vol.Optional('args'): vol.All(
    cv.ensure_list, vol.Length(min=1), [cv.string]
  ),
})

def setup(hass, config):
  """Initialize our component while Home Assistant loads."""
  from pyparticleio.ParticleCloud import ParticleCloud

  access_token = config[DOMAIN]['access_token']

  particle = hass.data[DOMAIN] = ParticleCloud(access_token)

  component = EntityComponent(_LOGGER, DOMAIN, hass)

  devices = {}
  device_list = []

  for name, info in particle.devices.items():
    entity_id = ('particle.' + name).lower()

    device = ParticleDevice(name, info)
    devices[entity_id] = device
    device_list.append(device)

  component.add_entities(device_list)
  component.async_register_entity_service(
    'call',
    FUNCTION_CALL_SCHEMA,
    ParticleDevice.call,
  )

  return True

class ParticleDevice(Entity):
  def __init__(self, name, info):
    self._name = name
    self._info = info
    self._attributes = {}

  @property
  def name(self):
    return self._name

  @property
  def icon(self):
    return 'mdi:star-four-points'

  @property
  def available(self):
    return self._info.connected

  @property
  def state(self):
    if self._info.connected:
      return STATE_ON
    else:
      return STATE_UNAVAILABLE

  def call(self, service):
    function = service.data.get('function')
    args = service.data.get('args', [])

    source = 'self._info.' + function + '(*args)'

    return eval(source, { 'self': self, 'args': args })

  @property
  def device_state_attributes(self):
    return self._attributes

  def update(self):
    if self._info.variables is not None:
      for name, _ in self._info.variables.items():
        source = 'self._info.' + name
        self._attributes[name] = eval(source, { 'self': self })
