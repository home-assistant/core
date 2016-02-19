"""
homeassistant.helpers.entity.

Provides ABC for entities in HA.
"""

import re
from collections import defaultdict

from homeassistant.const import (
    ATTR_ASSUMED_STATE, ATTR_FRIENDLY_NAME, ATTR_HIDDEN, ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT, DEVICE_DEFAULT_NAME, STATE_OFF, STATE_ON,
    STATE_UNAVAILABLE, STATE_UNKNOWN, TEMP_CELCIUS, TEMP_FAHRENHEIT)
from homeassistant.exceptions import NoEntitySpecifiedError
from homeassistant.util import ensure_unique_string, slugify

# Dict mapping entity_id to a boolean that overwrites the hidden property
_OVERWRITE = defaultdict(dict)

# Pattern for validating entity IDs (format: <domain>.<entity>)
ENTITY_ID_PATTERN = re.compile(r"^(\w+)\.(\w+)$")


def generate_entity_id(entity_id_format, name, current_ids=None, hass=None):
    """Generate a unique entity ID based on given entity IDs or used ids."""
    name = (name or DEVICE_DEFAULT_NAME).lower()
    if current_ids is None:
        if hass is None:
            raise RuntimeError("Missing required parameter currentids or hass")

        current_ids = hass.states.entity_ids()

    return ensure_unique_string(
        entity_id_format.format(slugify(name.lower())), current_ids)


def split_entity_id(entity_id):
    """Split a state entity_id into domain, object_id."""
    return entity_id.split(".", 1)


def valid_entity_id(entity_id):
    """Test if an entity ID is a valid format."""
    return ENTITY_ID_PATTERN.match(entity_id) is not None


class Entity(object):
    """ABC for Home Assistant entities."""

    # pylint: disable=no-self-use

    # SAFE TO OVERWRITE
    # The properties and methods here are safe to overwrite when inherting this
    # class. These may be used to customize the behavior of the entity.

    @property
    def should_poll(self):
        """
        Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return True

    @property
    def unique_id(self):
        """Return a unique id."""
        return "{}.{}".format(self.__class__, id(self))

    @property
    def name(self):
        """Return the name of the entity."""
        return None

    @property
    def state(self):
        """Return the state of the entity."""
        return STATE_UNKNOWN

    @property
    def state_attributes(self):
        """
        Return the state attributes.

        Implemented by component base class.
        """
        return None

    @property
    def device_state_attributes(self):
        """
        Return device specific state attributes.

        Implemented by platform classes.
        """
        return None

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return None

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return None

    @property
    def hidden(self):
        """Return True if the entity should be hidden from UIs."""
        return False

    @property
    def available(self):
        """Return True if entity is available."""
        return True

    @property
    def assumed_state(self):
        """Return True if unable to access real state of entity."""
        return False

    def update(self):
        """Retrieve latest state."""
        pass

    entity_id = None

    # DO NOT OVERWRITE
    # These properties and methods are either managed by Home Assistant or they
    # are used to perform a very specific function. Overwriting these may
    # produce undesirable effects in the entity's operation.

    hass = None

    def update_ha_state(self, force_refresh=False):
        """
        Update Home Assistant with current state of entity.

        If force_refresh == True will update entity before setting state.
        """
        if self.hass is None:
            raise RuntimeError("Attribute hass is None for {}".format(self))

        if self.entity_id is None:
            raise NoEntitySpecifiedError(
                "No entity id specified for entity {}".format(self.name))

        if force_refresh:
            self.update()

        state = STATE_UNKNOWN if self.state is None else str(self.state)
        attr = self.state_attributes or {}

        device_attr = self.device_state_attributes

        if device_attr is not None:
            attr.update(device_attr)

        if ATTR_UNIT_OF_MEASUREMENT not in attr and \
           self.unit_of_measurement is not None:
            attr[ATTR_UNIT_OF_MEASUREMENT] = str(self.unit_of_measurement)

        if not self.available:
            state = STATE_UNAVAILABLE
            attr = {}

        if self.name is not None:
            attr[ATTR_FRIENDLY_NAME] = str(self.name)

        if self.icon is not None:
            attr[ATTR_ICON] = str(self.icon)

        if self.hidden:
            attr[ATTR_HIDDEN] = bool(self.hidden)

        if self.assumed_state:
            attr[ATTR_ASSUMED_STATE] = bool(self.assumed_state)

        # overwrite properties that have been set in the config file
        attr.update(_OVERWRITE.get(self.entity_id, {}))

        # remove hidden property if false so it won't show up
        if not attr.get(ATTR_HIDDEN, True):
            attr.pop(ATTR_HIDDEN)

        # Convert temperature if we detect one
        if attr.get(ATTR_UNIT_OF_MEASUREMENT) in (TEMP_CELCIUS,
                                                  TEMP_FAHRENHEIT):

            state, attr[ATTR_UNIT_OF_MEASUREMENT] = \
                self.hass.config.temperature(
                    state, attr[ATTR_UNIT_OF_MEASUREMENT])
            state = str(state)

        return self.hass.states.set(self.entity_id, state, attr)

    def __eq__(self, other):
        return (isinstance(other, Entity) and
                other.unique_id == self.unique_id)

    def __repr__(self):
        return "<Entity {}: {}>".format(self.name, self.state)

    @staticmethod
    def overwrite_attribute(entity_id, attrs, vals):
        """
        Overwrite any attribute of an entity.

        This function should receive a list of attributes and a
        list of values. Set attribute to None to remove any overwritten
        value in place.
        """
        for attr, val in zip(attrs, vals):
            if val is None:
                _OVERWRITE[entity_id.lower()].pop(attr, None)
            else:
                _OVERWRITE[entity_id.lower()][attr] = val


class ToggleEntity(Entity):
    """ABC for entities that can be turned on and off."""

    # pylint: disable=no-self-use

    @property
    def state(self):
        """Return the state."""
        return STATE_ON if self.is_on else STATE_OFF

    @property
    def is_on(self):
        """True if entity is on."""
        return False

    def turn_on(self, **kwargs):
        """Turn the entity on."""
        pass

    def turn_off(self, **kwargs):
        """Turn the entity off."""
        pass

    def toggle(self, **kwargs):
        """Toggle the entity off."""
        if self.is_on:
            self.turn_off(**kwargs)
        else:
            self.turn_on(**kwargs)
