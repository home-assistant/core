"""Support for selects which integrates with other components."""
import voluptuous as vol

from homeassistant.components.select import PLATFORM_SCHEMA, SelectEntity
from homeassistant.components.select.const import ATTR_OPTION
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

CONF_SELECT_OPTION = "select_option"
CONF_OPTIONS_TEMPLATE = "options_template"

DEFAULT_NAME = "Template Select"
DEFAULT_OPTIMISTIC = False

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_VALUE_TEMPLATE): cv.template,
        vol.Required(CONF_SELECT_OPTION): cv.SCRIPT_SCHEMA,
        vol.Required(CONF_OPTIONS_TEMPLATE): cv.template,
        vol.Optional(CONF_AVAILABILITY_TEMPLATE): cv.template,
        vol.Optional(CONF_OPTIMISTIC, default=DEFAULT_OPTIMISTIC): cv.boolean,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)


async def _async_create_entities(hass, config):
    """Create the Template select."""
    return [
        TemplateSelect(
            hass,
            config[CONF_NAME],
            config[CONF_VALUE_TEMPLATE],
            config.get(CONF_AVAILABILITY_TEMPLATE),
            config[CONF_SELECT_OPTION],
            config[CONF_OPTIONS_TEMPLATE],
            config[CONF_OPTIMISTIC],
            config.get(CONF_UNIQUE_ID),
        )
    ]


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the template select."""
    async_add_entities(await _async_create_entities(hass, config))


class TemplateSelect(TemplateEntity, SelectEntity):
    """Representation of a template select."""

    def __init__(
        self,
        hass,
        name,
        value_template,
        availability_template,
        command_select_option,
        options_template,
        optimistic,
        unique_id,
    ):
        """Initialize the select."""
        super().__init__(availability_template=availability_template)
        self._attr_name = name
        self._value_template = value_template
        domain = __name__.split(".")[-2]
        self._command_select_option = Script(hass, command_select_option, name, domain)
        self._options_template = options_template
        self._attr_assumed_state = self._optimistic = optimistic
        self._attr_unique_id = unique_id
        self._attr_options = None
        self._attr_current_option = None

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.add_template_attribute(
            "_attr_current_option",
            self._value_template,
            validator=cv.string,
            none_on_template_error=True,
        )
        self.add_template_attribute(
            "_attr_options",
            self._options_template,
            validator=vol.All(cv.ensure_list, cv.string),
            none_on_template_error=True,
        )
        await super().async_added_to_hass()

    async def async_select_option(self, option):
        """Change the selected option."""
        if self._optimistic:
            self._attr_current_option = option
            self.async_write_ha_state()
        await self._command_select_option.async_run(
            {ATTR_OPTION: option}, context=self._context
        )
