"""Support for numbers which integrates with other components."""
import voluptuous as vol

from homeassistant.components.number import PLATFORM_SCHEMA, NumberEntity
from homeassistant.components.number.const import (
    ATTR_VALUE,
    DEFAULT_MAX_VALUE,
    DEFAULT_MIN_VALUE,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_OPTIMISTIC,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.script import Script

from .const import CONF_AVAILABILITY_TEMPLATE
from .template_entity import TemplateEntity

CONF_SET_VALUE = "set_value"
CONF_STEP_TEMPLATE = "step_template"
CONF_MINIMUM_TEMPLATE = "minimum_template"
CONF_MAXIMUM_TEMPLATE = "maximum_template"

DEFAULT_NAME = "Template Number"
DEFAULT_OPTIMISTIC = False

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_VALUE_TEMPLATE): cv.template,
        vol.Required(CONF_SET_VALUE): cv.SCRIPT_SCHEMA,
        vol.Required(CONF_STEP_TEMPLATE): cv.template,
        vol.Optional(CONF_MINIMUM_TEMPLATE): cv.template,
        vol.Optional(CONF_MAXIMUM_TEMPLATE): cv.template,
        vol.Optional(CONF_AVAILABILITY_TEMPLATE): cv.template,
        vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)


async def _async_create_entities(hass, config):
    """Create the Template number."""
    return [
        TemplateNumber(
            hass,
            config[CONF_NAME],
            config[CONF_VALUE_TEMPLATE],
            config.get(CONF_AVAILABILITY_TEMPLATE),
            config[CONF_SET_VALUE],
            config[CONF_STEP_TEMPLATE],
            config.get(CONF_MINIMUM_TEMPLATE),
            config.get(CONF_MAXIMUM_TEMPLATE),
            config[CONF_OPTIMISTIC],
            config.get(CONF_UNIQUE_ID),
        )
    ]


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the template number."""
    async_add_entities(await _async_create_entities(hass, config))


class TemplateNumber(TemplateEntity, NumberEntity):
    """Representation of a template number."""

    def __init__(
        self,
        hass,
        name,
        value_template,
        availability_template,
        command_set_value,
        step_template,
        minimum_template,
        maximum_template,
        optimistic,
        unique_id,
    ) -> None:
        """Initialize the number."""
        super().__init__(availability_template=availability_template)
        self._attr_name = name
        self._value_template = value_template
        domain = __name__.split(".")[-2]
        self._command_set_value = Script(hass, command_set_value, name, domain)
        self._step_template = step_template
        self._min_value_template = minimum_template
        if self._min_value_template is None:
            self._attr_min_value = DEFAULT_MIN_VALUE
        self._max_value_template = maximum_template
        if self._max_value_template is None:
            self._attr_max_value = DEFAULT_MAX_VALUE
        self._attr_assumed_state = self._optimistic = optimistic
        self._attr_unique_id = unique_id
        self._attr_value = None
        self._attr_step = None

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.add_template_attribute(
            "_attr_value",
            self._value_template,
            validator=vol.Coerce(float),
            none_on_template_error=True,
        )
        self.add_template_attribute(
            "_attr_step",
            self._step_template,
            validator=vol.Coerce(float),
            none_on_template_error=True,
        )
        if self._min_value_template is not None:
            self.add_template_attribute(
                "_attr_min_value",
                self._min_value_template,
                validator=vol.Coerce(float),
                none_on_template_error=True,
            )
        if self._max_value_template is not None:
            self.add_template_attribute(
                "_attr_max_value",
                self._max_value_template,
                validator=vol.Coerce(float),
                none_on_template_error=True,
            )
        await super().async_added_to_hass()

    async def async_set_value(self, value):
        """Set value of the number."""
        if self._optimistic:
            self._attr_value = value
            self.async_write_ha_state()
        await self._command_set_value.async_run(
            {ATTR_VALUE: value}, context=self._context
        )
