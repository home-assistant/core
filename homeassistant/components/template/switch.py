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
    CONF_VALUE_TEMPLATE,
    EVENT_HOMEASSISTANT_START,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import callback
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.event import async_track_state_change
from homeassistant.helpers.script import Script

from . import extract_entities, initialise_templates
from .const import CONF_AVAILABILITY_TEMPLATE

_LOGGER = logging.getLogger(__name__)
_VALID_STATES = [STATE_ON, STATE_OFF, "true", "false"]

ON_ACTION = "turn_on"
OFF_ACTION = "turn_off"

SWITCH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_ICON_TEMPLATE): cv.template,
        vol.Optional(CONF_ENTITY_PICTURE_TEMPLATE): cv.template,
        vol.Optional(CONF_AVAILABILITY_TEMPLATE): cv.template,
        vol.Required(ON_ACTION): cv.SCRIPT_SCHEMA,
        vol.Required(OFF_ACTION): cv.SCRIPT_SCHEMA,
        vol.Optional(ATTR_FRIENDLY_NAME): cv.string,
        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_SWITCHES): cv.schema_with_slug_keys(SWITCH_SCHEMA)}
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Template switch."""
    switches = []

    for device, device_config in config[CONF_SWITCHES].items():
        friendly_name = device_config.get(ATTR_FRIENDLY_NAME, device)
        state_template = device_config[CONF_VALUE_TEMPLATE]
        icon_template = device_config.get(CONF_ICON_TEMPLATE)
        entity_picture_template = device_config.get(CONF_ENTITY_PICTURE_TEMPLATE)
        availability_template = device_config.get(CONF_AVAILABILITY_TEMPLATE)
        on_action = device_config[ON_ACTION]
        off_action = device_config[OFF_ACTION]

        templates = {
            CONF_VALUE_TEMPLATE: state_template,
            CONF_ICON_TEMPLATE: icon_template,
            CONF_ENTITY_PICTURE_TEMPLATE: entity_picture_template,
            CONF_AVAILABILITY_TEMPLATE: availability_template,
        }

        initialise_templates(hass, templates)
        entity_ids = extract_entities(
            device, "switch", device_config.get(ATTR_ENTITY_ID), templates
        )

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
                entity_ids,
            )
        )

    async_add_entities(switches)


class SwitchTemplate(SwitchEntity):
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
        entity_ids,
    ):
        """Initialize the Template switch."""
        self.hass = hass
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, device_id, hass=hass
        )
        self._name = friendly_name
        self._template = state_template
        self._on_script = Script(hass, on_action)
        self._off_script = Script(hass, off_action)
        self._state = False
        self._icon_template = icon_template
        self._entity_picture_template = entity_picture_template
        self._availability_template = availability_template
        self._icon = None
        self._entity_picture = None
        self._entities = entity_ids
        self._available = True

    async def async_added_to_hass(self):
        """Register callbacks."""

        @callback
        def template_switch_state_listener(entity, old_state, new_state):
            """Handle target device state changes."""
            self.async_schedule_update_ha_state(True)

        @callback
        def template_switch_startup(event):
            """Update template on startup."""
            async_track_state_change(
                self.hass, self._entities, template_switch_state_listener
            )

            self.async_schedule_update_ha_state(True)

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, template_switch_startup
        )

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self._icon

    @property
    def entity_picture(self):
        """Return the entity_picture to use in the frontend, if any."""
        return self._entity_picture

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return self._available

    async def async_turn_on(self, **kwargs):
        """Fire the on action."""
        await self._on_script.async_run(context=self._context)

    async def async_turn_off(self, **kwargs):
        """Fire the off action."""
        await self._off_script.async_run(context=self._context)

    async def async_update(self):
        """Update the state from the template."""
        try:
            state = self._template.async_render().lower()

            if state in _VALID_STATES:
                self._state = state in ("true", STATE_ON)
            else:
                _LOGGER.error(
                    "Received invalid switch is_on state: %s. Expected: %s",
                    state,
                    ", ".join(_VALID_STATES),
                )
                self._state = None

        except TemplateError as ex:
            _LOGGER.error(ex)
            self._state = None

        for property_name, template in (
            ("_icon", self._icon_template),
            ("_entity_picture", self._entity_picture_template),
            ("_available", self._availability_template),
        ):
            if template is None:
                continue

            try:
                value = template.async_render()
                if property_name == "_available":
                    value = value.lower() == "true"
                setattr(self, property_name, value)
            except TemplateError as ex:
                friendly_property_name = property_name[1:].replace("_", " ")
                if ex.args and ex.args[0].startswith(
                    "UndefinedError: 'None' has no attribute"
                ):
                    # Common during HA startup - so just a warning
                    _LOGGER.warning(
                        "Could not render %s template %s, the state is unknown",
                        friendly_property_name,
                        self._name,
                    )
                    return

                try:
                    setattr(self, property_name, getattr(super(), property_name))
                except AttributeError:
                    _LOGGER.error(
                        "Could not render %s template %s: %s",
                        friendly_property_name,
                        self._name,
                        ex,
                    )
