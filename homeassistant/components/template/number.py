"""Support for numbers which integrates with other components."""
import voluptuous as vol

from homeassistant.components.number import NumberEntity
from homeassistant.components.number.const import (
    ATTR_MAX,
    ATTR_MIN,
    ATTR_STEP,
    ATTR_VALUE,
    DEFAULT_MAX_VALUE,
    DEFAULT_MIN_VALUE,
)
from homeassistant.const import CONF_NAME, CONF_OPTIMISTIC, CONF_STATE, CONF_UNIQUE_ID
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.script import Script

from .const import CONF_ATTRIBUTES, CONF_AVAILABILITY
from .template_entity import TemplateEntity

CONF_SET_VALUE = "set_value"

DEFAULT_NAME = "Template Number"
DEFAULT_OPTIMISTIC = False

NUMBER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_STATE): cv.template,
        vol.Required(CONF_SET_VALUE): cv.SCRIPT_SCHEMA,
        vol.Required(CONF_ATTRIBUTES): vol.Schema(
            {
                vol.Required(ATTR_STEP): cv.template,
                vol.Optional(ATTR_MIN): cv.template,
                vol.Optional(ATTR_MAX): cv.template,
            }
        ),
        vol.Optional(CONF_AVAILABILITY): cv.template,
        vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)


async def _async_create_entities(hass, definitions, unique_id_prefix):
    """Create the Template number."""
    entities = []
    for definition in definitions:
        unique_id = definition.get(CONF_UNIQUE_ID)
        if unique_id and unique_id_prefix:
            unique_id = f"{unique_id_prefix}-{unique_id}"
        entities.append(
            TemplateNumber(
                hass,
                definition[CONF_NAME],
                definition[CONF_STATE],
                definition.get(CONF_AVAILABILITY),
                definition[CONF_SET_VALUE],
                definition[CONF_ATTRIBUTES][ATTR_STEP],
                definition[CONF_ATTRIBUTES].get(ATTR_MIN),
                definition[CONF_ATTRIBUTES].get(ATTR_MAX),
                definition[CONF_OPTIMISTIC],
                unique_id,
            )
        )
    return entities


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the template number."""
    async_add_entities(
        await _async_create_entities(
            hass, discovery_info["entities"], discovery_info["unique_id"]
        )
    )


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
