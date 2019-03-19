"""Support to set a numeric value from a slider or text box."""
import logging

import voluptuous as vol

from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_UNIT_OF_MEASUREMENT, CONF_ENTITY_ID, CONF_ICON,
    CONF_NAME, CONF_MODE, CONF_VALUE_TEMPLATE, EVENT_HOMEASSISTANT_START,
    MATCH_ALL)
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.script import Script

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'input_number'
ENTITY_ID_FORMAT = DOMAIN + '.{}'

CONF_INITIAL = 'initial'
CONF_MIN = 'min'
CONF_MAX = 'max'
CONF_STEP = 'step'
CONF_SET_VALUE = 'set_value_script'

MODE_SLIDER = 'slider'
MODE_BOX = 'box'

ATTR_INITIAL = 'initial'
ATTR_VALUE = 'value'
ATTR_MIN = 'min'
ATTR_MAX = 'max'
ATTR_STEP = 'step'
ATTR_MODE = 'mode'

SERVICE_SET_VALUE = 'set_value'
SERVICE_INCREMENT = 'increment'
SERVICE_DECREMENT = 'decrement'

SERVICE_DEFAULT_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids
})

SERVICE_SET_VALUE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_VALUE): vol.Coerce(float),
})


def _cv_input_number(cfg):
    """Configure validation helper for input number (voluptuous)."""
    minimum = cfg.get(CONF_MIN)
    maximum = cfg.get(CONF_MAX)
    if minimum >= maximum:
        raise vol.Invalid('Maximum ({}) is not greater than minimum ({})'
                          .format(minimum, maximum))
    state = cfg.get(CONF_INITIAL)
    if state is not None and (state < minimum or state > maximum):
        raise vol.Invalid('Initial value {} not in range {}-{}'
                          .format(state, minimum, maximum))
    if (CONF_VALUE_TEMPLATE in cfg) is (CONF_SET_VALUE not in cfg):
        raise vol.Invalid('{} and {} must be provided together'
                          .format(CONF_VALUE_TEMPLATE, CONF_SET_VALUE))
    return cfg


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: cv.schema_with_slug_keys(
        vol.All({
            vol.Optional(CONF_NAME): cv.string,
            vol.Required(CONF_MIN): vol.Coerce(float),
            vol.Required(CONF_MAX): vol.Coerce(float),
            vol.Optional(CONF_INITIAL): vol.Coerce(float),
            vol.Optional(CONF_STEP, default=1):
                vol.All(vol.Coerce(float), vol.Range(min=1e-3)),
            vol.Optional(CONF_ICON): cv.icon,
            vol.Optional(ATTR_UNIT_OF_MEASUREMENT): cv.string,
            vol.Optional(CONF_MODE, default=MODE_SLIDER):
                vol.In([MODE_BOX, MODE_SLIDER]),
            vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
            vol.Optional(CONF_SET_VALUE): cv.SCRIPT_SCHEMA,
            vol.Optional(CONF_ENTITY_ID): cv.entity_ids
        }, _cv_input_number)
    )
}, required=True, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up an input slider."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    entities = []

    for object_id, cfg in config[DOMAIN].items():
        name = cfg.get(CONF_NAME)
        minimum = cfg.get(CONF_MIN)
        maximum = cfg.get(CONF_MAX)
        initial = cfg.get(CONF_INITIAL)
        step = cfg.get(CONF_STEP)
        icon = cfg.get(CONF_ICON)
        unit = cfg.get(ATTR_UNIT_OF_MEASUREMENT)
        mode = cfg.get(CONF_MODE)
        template = cfg.get(CONF_VALUE_TEMPLATE)
        value_script = cfg.get(CONF_SET_VALUE)
        _LOGGER.critical(value_script)

        template_entity_ids = set()

        if template is not None:
            temp_ids = template.extract_entities()
            if str(temp_ids) != MATCH_ALL:
                template_entity_ids |= set(temp_ids)

        entity_ids = cfg.get(CONF_ENTITY_ID, template_entity_ids)

        entities.append(InputNumber(
            hass, object_id, name, initial, minimum, maximum, step, icon, unit,
            mode, template, value_script, entity_ids))

    if not entities:
        return False

    component.async_register_entity_service(
        SERVICE_SET_VALUE, SERVICE_SET_VALUE_SCHEMA,
        'async_set_value'
    )

    component.async_register_entity_service(
        SERVICE_INCREMENT, SERVICE_DEFAULT_SCHEMA,
        'async_increment'
    )

    component.async_register_entity_service(
        SERVICE_DECREMENT, SERVICE_DEFAULT_SCHEMA,
        'async_decrement'
    )

    await component.async_add_entities(entities)
    return True


class InputNumber(RestoreEntity):
    """Representation of a slider."""

    def __init__(self, hass, object_id, name, initial, minimum, maximum, step,
                 icon, unit, mode, template, value_script, entity_ids):
        """Initialize an input number."""
        self.hass = hass
        self.entity_id = ENTITY_ID_FORMAT.format(object_id)
        self._name = name
        self._current_value = initial
        self._initial = initial
        self._minimum = minimum
        self._maximum = maximum
        self._step = step
        self._icon = icon
        self._unit = unit
        self._mode = mode
        self._entities = entity_ids

        if value_script:
            self._value_script = Script(hass, value_script)
        else:
            self._value_script = None

        self._template = template
        if self._template is not None:
            self._template.hass = self.hass

    @property
    def should_poll(self):
        """If entity should be polled."""
        return False

    @property
    def name(self):
        """Return the name of the input slider."""
        return self._name

    @property
    def icon(self):
        """Return the icon to be used for this entity."""
        return self._icon

    @property
    def state(self):
        """Return the state of the component."""
        return self._current_value

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_INITIAL: self._initial,
            ATTR_MIN: self._minimum,
            ATTR_MAX: self._maximum,
            ATTR_STEP: self._step,
            ATTR_MODE: self._mode,
        }

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass and register callbacks."""
        @callback
        def input_number_state_listener(entity, old_state, new_state):
            """Handle target device state changes."""
            self.async_schedule_update_ha_state(True)

        @callback
        def input_number_startup(event):
            """Update template on startup."""
            if self._template is not None:
                async_track_state_change(
                    self.hass, self._entities, input_number_state_listener)

            self.async_schedule_update_ha_state(True)

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, input_number_startup)

        await super().async_added_to_hass()
        if self._current_value is not None:
            return

        state = await self.async_get_last_state()
        value = state and float(state.state)

        # Check against None because value can be 0
        if value is not None and self._minimum <= value <= self._maximum:
            self._current_value = value
        else:
            self._current_value = self._minimum

    async def async_set_value(self, value):
        """Set new value."""
        num_value = float(value)
        if num_value < self._minimum or num_value > self._maximum:
            _LOGGER.warning("Invalid value: %s (range %s - %s)",
                            num_value, self._minimum, self._maximum)
            return
        self._current_value = num_value

        if self._template:
            await self._value_script.async_run(
                {"value": num_value}, context=self._context)
        await self.async_update_ha_state()

    async def async_increment(self):
        """Increment value."""
        new_value = self._current_value + self._step
        if new_value > self._maximum:
            _LOGGER.warning("Invalid value: %s (range %s - %s)",
                            new_value, self._minimum, self._maximum)
            return
        self._current_value = new_value
        if self._template:
            await self._value_script.async_run(
                {"value": new_value}, context=self._context)
        await self.async_update_ha_state()

    async def async_decrement(self):
        """Decrement value."""
        new_value = self._current_value - self._step
        if new_value < self._minimum:
            _LOGGER.warning("Invalid value: %s (range %s - %s)",
                            new_value, self._minimum, self._maximum)
            return
        self._current_value = new_value
        if self._template:
            await self._value_script.async_run(
                {"value": new_value}, context=self._context)
        await self.async_update_ha_state()

    async def async_update(self):
        """Update the state from the template."""
        if self._template is not None:
            try:
                self._current_value = float(self._template.async_render())
            except TemplateError as ex:
                _LOGGER.error(ex)
