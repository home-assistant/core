"""Helper classes for Google Assistant integration."""
from asyncio import gather
from collections.abc import Mapping

from homeassistant.core import Context, callback
from homeassistant.const import (
    CONF_NAME, STATE_UNAVAILABLE, ATTR_SUPPORTED_FEATURES,
    ATTR_DEVICE_CLASS
)

from . import trait
from .const import (
    DOMAIN_TO_GOOGLE_TYPES, CONF_ALIASES, ERR_FUNCTION_NOT_SUPPORTED,
    DEVICE_CLASS_TO_GOOGLE_TYPES, CONF_ROOM_HINT,
)
from .error import SmartHomeError


class Config:
    """Hold the configuration for Google Assistant."""

    def __init__(self, should_expose,
                 entity_config=None, secure_devices_pin=None):
        """Initialize the configuration."""
        self.should_expose = should_expose
        self.entity_config = entity_config or {}
        self.secure_devices_pin = secure_devices_pin


class RequestData:
    """Hold data associated with a particular request."""

    def __init__(self, config, user_id, request_id):
        """Initialize the request data."""
        self.config = config
        self.request_id = request_id
        self.context = Context(user_id=user_id)


def get_google_type(domain, device_class):
    """Google type based on domain and device class."""
    typ = DEVICE_CLASS_TO_GOOGLE_TYPES.get((domain, device_class))

    return typ if typ is not None else DOMAIN_TO_GOOGLE_TYPES[domain]


class GoogleEntity:
    """Adaptation of Entity expressed in Google's terms."""

    def __init__(self, hass, config, state):
        """Initialize a Google entity."""
        self.hass = hass
        self.config = config
        self.state = state
        self._traits = None

    @property
    def entity_id(self):
        """Return entity ID."""
        return self.state.entity_id

    @callback
    def traits(self):
        """Return traits for entity."""
        if self._traits is not None:
            return self._traits

        state = self.state
        domain = state.domain
        features = state.attributes.get(ATTR_SUPPORTED_FEATURES, 0)
        device_class = state.attributes.get(ATTR_DEVICE_CLASS)

        self._traits = [Trait(self.hass, state, self.config)
                        for Trait in trait.TRAITS
                        if Trait.supported(domain, features, device_class)]
        return self._traits

    async def sync_serialize(self):
        """Serialize entity for a SYNC response.

        https://developers.google.com/actions/smarthome/create-app#actiondevicessync
        """
        state = self.state

        # When a state is unavailable, the attributes that describe
        # capabilities will be stripped. For example, a light entity will miss
        # the min/max mireds. Therefore they will be excluded from a sync.
        if state.state == STATE_UNAVAILABLE:
            return None

        entity_config = self.config.entity_config.get(state.entity_id, {})
        name = (entity_config.get(CONF_NAME) or state.name).strip()
        domain = state.domain
        device_class = state.attributes.get(ATTR_DEVICE_CLASS)

        # If an empty string
        if not name:
            return None

        traits = self.traits()

        # Found no supported traits for this entity
        if not traits:
            return None

        device_type = get_google_type(domain,
                                      device_class)

        device = {
            'id': state.entity_id,
            'name': {
                'name': name
            },
            'attributes': {},
            'traits': [trait.name for trait in traits],
            'willReportState': False,
            'type': device_type,
        }

        # use aliases
        aliases = entity_config.get(CONF_ALIASES)
        if aliases:
            device['name']['nicknames'] = aliases

        for trt in traits:
            device['attributes'].update(trt.sync_attributes())

        room = entity_config.get(CONF_ROOM_HINT)
        if room:
            device['roomHint'] = room
            return device

        dev_reg, ent_reg, area_reg = await gather(
            self.hass.helpers.device_registry.async_get_registry(),
            self.hass.helpers.entity_registry.async_get_registry(),
            self.hass.helpers.area_registry.async_get_registry(),
        )

        entity_entry = ent_reg.async_get(state.entity_id)
        if not (entity_entry and entity_entry.device_id):
            return device

        device_entry = dev_reg.devices.get(entity_entry.device_id)
        if not (device_entry and device_entry.area_id):
            return device

        area_entry = area_reg.areas.get(device_entry.area_id)
        if area_entry and area_entry.name:
            device['roomHint'] = area_entry.name

        return device

    @callback
    def query_serialize(self):
        """Serialize entity for a QUERY response.

        https://developers.google.com/actions/smarthome/create-app#actiondevicesquery
        """
        state = self.state

        if state.state == STATE_UNAVAILABLE:
            return {'online': False}

        attrs = {'online': True}

        for trt in self.traits():
            deep_update(attrs, trt.query_attributes())

        return attrs

    async def execute(self, data, command_payload):
        """Execute a command.

        https://developers.google.com/actions/smarthome/create-app#actiondevicesexecute
        """
        command = command_payload['command']
        params = command_payload.get('params', {})
        challenge = command_payload.get('challenge', {})
        executed = False
        for trt in self.traits():
            if trt.can_execute(command, params):
                await trt.execute(command, data, params, challenge)
                executed = True
                break

        if not executed:
            raise SmartHomeError(
                ERR_FUNCTION_NOT_SUPPORTED,
                'Unable to execute {} for {}'.format(command,
                                                     self.state.entity_id))

    @callback
    def async_update(self):
        """Update the entity with latest info from Home Assistant."""
        self.state = self.hass.states.get(self.entity_id)

        if self._traits is None:
            return

        for trt in self._traits:
            trt.state = self.state


def deep_update(target, source):
    """Update a nested dictionary with another nested dictionary."""
    for key, value in source.items():
        if isinstance(value, Mapping):
            target[key] = deep_update(target.get(key, {}), value)
        else:
            target[key] = value
    return target
