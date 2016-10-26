"""
Component to offer a way to select a value from a slider.

For more details about this component, please refer to the documentation
at https://home-assistant.io/components/input_slider/
"""
import logging

import voluptuous as vol

from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_UNIT_OF_MEASUREMENT, CONF_ICON, CONF_NAME)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent

DOMAIN = 'input_slider'
ENTITY_ID_FORMAT = DOMAIN + '.{}'
_LOGGER = logging.getLogger(__name__)

CONF_INITIAL = 'initial'
CONF_MIN = 'min'
CONF_MAX = 'max'
CONF_STEP = 'step'

ATTR_VALUE = 'value'
ATTR_MIN = 'min'
ATTR_MAX = 'max'
ATTR_STEP = 'step'

SERVICE_SELECT_VALUE = 'select_value'

SERVICE_SELECT_VALUE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_VALUE): vol.Coerce(float),
})


def _cv_input_slider(cfg):
    """Config validation helper for input slider (Voluptuous)."""
    minimum = cfg.get(CONF_MIN)
    maximum = cfg.get(CONF_MAX)
    if minimum >= maximum:
        raise vol.Invalid('Maximum ({}) is not greater than minimum ({})'
                          .format(minimum, maximum))
    state = cfg.get(CONF_INITIAL, minimum)
    if state < minimum or state > maximum:
        raise vol.Invalid('Initial value {} not in range {}-{}'
                          .format(state, minimum, maximum))
    cfg[CONF_INITIAL] = state
    return cfg

CONFIG_SCHEMA = vol.Schema({DOMAIN: {
    cv.slug: vol.All({
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_MIN): vol.Coerce(float),
        vol.Required(CONF_MAX): vol.Coerce(float),
        vol.Optional(CONF_INITIAL): vol.Coerce(float),
        vol.Optional(CONF_STEP, default=1): vol.All(vol.Coerce(float),
                                                    vol.Range(min=1e-3)),
        vol.Optional(CONF_ICON): cv.icon,
        vol.Optional(ATTR_UNIT_OF_MEASUREMENT): cv.string
    }, _cv_input_slider)}}, required=True, extra=vol.ALLOW_EXTRA)


def select_value(hass, entity_id, value):
    """Set input_slider to value."""
    hass.services.call(DOMAIN, SERVICE_SELECT_VALUE, {
        ATTR_ENTITY_ID: entity_id,
        ATTR_VALUE: value,
    })


def setup(hass, config):
    """Set up input slider."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    entities = []

    for object_id, cfg in config[DOMAIN].items():
        name = cfg.get(CONF_NAME)
        minimum = cfg.get(CONF_MIN)
        maximum = cfg.get(CONF_MAX)
        state = cfg.get(CONF_INITIAL, minimum)
        step = cfg.get(CONF_STEP)
        icon = cfg.get(CONF_ICON)
        unit = cfg.get(ATTR_UNIT_OF_MEASUREMENT)

        entities.append(InputSlider(object_id, name, state, minimum, maximum,
                                    step, icon, unit))

    if not entities:
        return False

    def select_value_service(call):
        """Handle a calls to the input slider services."""
        target_inputs = component.extract_from_service(call)

        for input_slider in target_inputs:
            input_slider.select_value(call.data[ATTR_VALUE])

    hass.services.register(DOMAIN, SERVICE_SELECT_VALUE,
                           select_value_service,
                           schema=SERVICE_SELECT_VALUE_SCHEMA)

    component.add_entities(entities)

    return True


class InputSlider(Entity):
    """Represent an slider."""

    # pylint: disable=too-many-arguments, too-many-instance-attributes
    def __init__(self, object_id, name, state, minimum, maximum, step, icon,
                 unit):
        """Initialize a select input."""
        self.entity_id = ENTITY_ID_FORMAT.format(object_id)
        self._name = name
        self._current_value = state
        self._minimum = minimum
        self._maximum = maximum
        self._step = step
        self._icon = icon
        self._unit = unit

    @property
    def should_poll(self):
        """If entity should be polled."""
        return False

    @property
    def name(self):
        """Name of the select input."""
        return self._name

    @property
    def icon(self):
        """Icon to be used for this entity."""
        return self._icon

    @property
    def state(self):
        """State of the component."""
        return self._current_value

    @property
    def unit_of_measurement(self):
        """Unit of measurement of slider."""
        return self._unit

    @property
    def state_attributes(self):
        """State attributes."""
        return {
            ATTR_MIN: self._minimum,
            ATTR_MAX: self._maximum,
            ATTR_STEP: self._step
        }

    def select_value(self, value):
        """Select new value."""
        num_value = float(value)
        if num_value < self._minimum or num_value > self._maximum:
            _LOGGER.warning('Invalid value: %s (range %s - %s)',
                            num_value, self._minimum, self._maximum)
            return
        self._current_value = num_value
        self.update_ha_state()
