"""Support for switches which integrates with other components."""
import logging

import voluptuous as vol

from homeassistant.components.switch import (
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA,
    SwitchEntity,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    CONF_ENTITY_PICTURE_TEMPLATE,
    CONF_ICON_TEMPLATE,
    CONF_SWITCHES,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import callback
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.script import Script

from .const import CONF_AVAILABILITY_TEMPLATE, DOMAIN, PLATFORMS
from .template_entity import TemplateEntity

_LOGGER = logging.getLogger(__name__)
_VALID_STATES = [STATE_ON, STATE_OFF, "true", "false"]

ON_ACTION = "turn_on"
OFF_ACTION = "turn_off"

SWITCH_SCHEMA = vol.All(
    cv.deprecated(ATTR_ENTITY_ID),
    vol.Schema(
        {
            vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
            vol.Optional(CONF_ICON_TEMPLATE): cv.template,
            vol.Optional(CONF_ENTITY_PICTURE_TEMPLATE): cv.template,
            vol.Optional(CONF_AVAILABILITY_TEMPLATE): cv.template,
            vol.Required(ON_ACTION): cv.SCRIPT_SCHEMA,
            vol.Required(OFF_ACTION): cv.SCRIPT_SCHEMA,
            vol.Optional(ATTR_FRIENDLY_NAME): cv.string,
            vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
            vol.Optional(CONF_UNIQUE_ID): cv.string,
        }
    ),
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_SWITCHES): cv.schema_with_slug_keys(SWITCH_SCHEMA)}
)


async def _async_create_entities(hass, config):
    """Create the Template switches."""
    switches = []

    for device, device_config in config[CONF_SWITCHES].items():
        friendly_name = device_config.get(ATTR_FRIENDLY_NAME, device)
        state_template = device_config.get(CONF_VALUE_TEMPLATE)
        icon_template = device_config.get(CONF_ICON_TEMPLATE)
        entity_picture_template = device_config.get(CONF_ENTITY_PICTURE_TEMPLATE)
        availability_template = device_config.get(CONF_AVAILABILITY_TEMPLATE)
        on_action = device_config[ON_ACTION]
        off_action = device_config[OFF_ACTION]
        unique_id = device_config.get(CONF_UNIQUE_ID)

        switches.append(
            SwitchTemplate(
                hass,
                device,
                friendly_name,
                state_template,
                icon_template,
                entity_picture_template,
                availability_template,
                on_action,
                off_action,
                unique_id,
            )
        )

    return switches


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the template switches."""

    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)
    async_add_entities(await _async_create_entities(hass, config))


class SwitchTemplate(TemplateEntity, SwitchEntity, RestoreEntity):
    """Representation of a Template switch."""

    def __init__(
        self,
        hass,
        device_id,
        friendly_name,
        state_template,
        icon_template,
        entity_picture_template,
        availability_template,
        on_action,
        off_action,
        unique_id,
    ):
        """Initialize the Template switch."""
        super().__init__(
            availability_template=availability_template,
            icon_template=icon_template,
            entity_picture_template=entity_picture_template,
        )
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, device_id, hass=hass
        )
        self._name = friendly_name
        self._template = state_template
        domain = __name__.split(".")[-2]
        self._on_script = Script(hass, on_action, friendly_name, domain)
        self._off_script = Script(hass, off_action, friendly_name, domain)
        self._state = False
        self._unique_id = unique_id

    @callback
    def _update_state(self, result):
        super()._update_state(result)
        if isinstance(result, TemplateError):
            self._state = None
            return
        self._state = result.lower() in ("true", STATE_ON)

    async def async_added_to_hass(self):
        """Register callbacks."""

        if self._template is None:

            # restore state after startup
            await super().async_added_to_hass()
            state = await self.async_get_last_state()
            if state:
                self._state = state.state == STATE_ON

            # no need to listen for events
        else:
            self.add_template_attribute(
                "_state", self._template, None, self._update_state
            )

        await super().async_added_to_hass()

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id of this switch."""
        return self._unique_id

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    async def async_turn_on(self, **kwargs):
        """Fire the on action."""
        await self._on_script.async_run(context=self._context)
        if self._template is None:
            self._state = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Fire the off action."""
        await self._off_script.async_run(context=self._context)
        if self._template is None:
            self._state = False
            self.async_write_ha_state()

    @property
    def assumed_state(self):
        """State is assumed, if no template given."""
        return self._template is None
