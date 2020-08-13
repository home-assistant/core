"""Support for exposing a templated binary sensor."""
import logging

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA,
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    CONF_DEVICE_CLASS,
    CONF_ENTITY_PICTURE_TEMPLATE,
    CONF_ICON_TEMPLATE,
    CONF_SENSORS,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
    EVENT_HOMEASSISTANT_START,
    MATCH_ALL,
)
from homeassistant.core import callback
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.event import (
    async_track_same_state,
    async_track_state_change_event,
)

from . import extract_entities, initialise_templates
from .const import CONF_AVAILABILITY_TEMPLATE

_LOGGER = logging.getLogger(__name__)

CONF_DELAY_ON = "delay_on"
CONF_DELAY_OFF = "delay_off"
CONF_ATTRIBUTE_TEMPLATES = "attribute_templates"

SENSOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_ICON_TEMPLATE): cv.template,
        vol.Optional(CONF_ENTITY_PICTURE_TEMPLATE): cv.template,
        vol.Optional(CONF_AVAILABILITY_TEMPLATE): cv.template,
        vol.Optional(CONF_ATTRIBUTE_TEMPLATES): vol.Schema({cv.string: cv.template}),
        vol.Optional(ATTR_FRIENDLY_NAME): cv.string,
        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_DELAY_ON): cv.positive_time_period,
        vol.Optional(CONF_DELAY_OFF): cv.positive_time_period,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_SENSORS): cv.schema_with_slug_keys(SENSOR_SCHEMA)}
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up template binary sensors."""
    sensors = []

    for device, device_config in config[CONF_SENSORS].items():
        value_template = device_config[CONF_VALUE_TEMPLATE]
        icon_template = device_config.get(CONF_ICON_TEMPLATE)
        entity_picture_template = device_config.get(CONF_ENTITY_PICTURE_TEMPLATE)
        availability_template = device_config.get(CONF_AVAILABILITY_TEMPLATE)
        attribute_templates = device_config.get(CONF_ATTRIBUTE_TEMPLATES, {})

        friendly_name = device_config.get(ATTR_FRIENDLY_NAME, device)
        device_class = device_config.get(CONF_DEVICE_CLASS)
        delay_on = device_config.get(CONF_DELAY_ON)
        delay_off = device_config.get(CONF_DELAY_OFF)
        unique_id = device_config.get(CONF_UNIQUE_ID)

        templates = {
            CONF_VALUE_TEMPLATE: value_template,
            CONF_ICON_TEMPLATE: icon_template,
            CONF_ENTITY_PICTURE_TEMPLATE: entity_picture_template,
            CONF_AVAILABILITY_TEMPLATE: availability_template,
        }

        initialise_templates(hass, templates, attribute_templates)
        entity_ids = extract_entities(
            device,
            "binary sensor",
            device_config.get(ATTR_ENTITY_ID),
            templates,
            attribute_templates,
        )

        sensors.append(
            BinarySensorTemplate(
                hass,
                device,
                friendly_name,
                device_class,
                value_template,
                icon_template,
                entity_picture_template,
                availability_template,
                entity_ids,
                delay_on,
                delay_off,
                attribute_templates,
                unique_id,
            )
        )

    async_add_entities(sensors)


class BinarySensorTemplate(BinarySensorEntity):
    """A virtual binary sensor that triggers from another sensor."""

    def __init__(
        self,
        hass,
        device,
        friendly_name,
        device_class,
        value_template,
        icon_template,
        entity_picture_template,
        availability_template,
        entity_ids,
        delay_on,
        delay_off,
        attribute_templates,
        unique_id,
    ):
        """Initialize the Template binary sensor."""
        self.hass = hass
        self.entity_id = async_generate_entity_id(ENTITY_ID_FORMAT, device, hass=hass)
        self._name = friendly_name
        self._device_class = device_class
        self._template = value_template
        self._state = None
        self._icon_template = icon_template
        self._availability_template = availability_template
        self._entity_picture_template = entity_picture_template
        self._icon = None
        self._entity_picture = None
        self._entities = entity_ids
        self._delay_on = delay_on
        self._delay_off = delay_off
        self._available = True
        self._attribute_templates = attribute_templates
        self._attributes = {}
        self._unique_id = unique_id

    async def async_added_to_hass(self):
        """Register callbacks."""

        @callback
        def template_bsensor_state_listener(event):
            """Handle the target device state changes."""
            self.async_check_state()

        @callback
        def template_bsensor_startup(event):
            """Update template on startup."""
            if self._entities != MATCH_ALL:
                # Track state change only for valid templates
                async_track_state_change_event(
                    self.hass, self._entities, template_bsensor_state_listener
                )

            self.async_check_state()

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, template_bsensor_startup
        )

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id of this binary sensor."""
        return self._unique_id

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return self._icon

    @property
    def entity_picture(self):
        """Return the entity_picture to use in the frontend, if any."""
        return self._entity_picture

    @property
    def is_on(self):
        """Return true if sensor is on."""
        return self._state

    @property
    def device_class(self):
        """Return the sensor class of the sensor."""
        return self._device_class

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def available(self):
        """Availability indicator."""
        return self._available

    @callback
    def _async_render(self):
        """Get the state of template."""
        state = None
        try:
            state = self._template.async_render().lower() == "true"
        except TemplateError as ex:
            if ex.args and ex.args[0].startswith(
                "UndefinedError: 'None' has no attribute"
            ):
                # Common during HA startup - so just a warning
                _LOGGER.warning(
                    "Could not render template %s, the state is unknown", self._name
                )
                return
            _LOGGER.error("Could not render template %s: %s", self._name, ex)

        attrs = {}
        if self._attribute_templates is not None:
            for key, value in self._attribute_templates.items():
                try:
                    attrs[key] = value.async_render()
                except TemplateError as err:
                    _LOGGER.error("Error rendering attribute %s: %s", key, err)
            self._attributes = attrs

        templates = {
            "_icon": self._icon_template,
            "_entity_picture": self._entity_picture_template,
            "_available": self._availability_template,
        }

        for property_name, template in templates.items():
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
                else:
                    _LOGGER.error(
                        "Could not render %s template %s: %s",
                        friendly_property_name,
                        self._name,
                        ex,
                    )
                return state

        return state

    @callback
    def async_check_state(self):
        """Update the state from the template."""
        state = self._async_render()

        # return if the state don't change or is invalid
        if state is None or state == self.state:
            return

        @callback
        def set_state():
            """Set state of template binary sensor."""
            self._state = state
            self.async_write_ha_state()

        # state without delay
        if (state and not self._delay_on) or (not state and not self._delay_off):
            set_state()
            return

        period = self._delay_on if state else self._delay_off
        async_track_same_state(
            self.hass,
            period,
            set_state,
            entity_ids=self._entities,
            async_check_same_func=lambda *args: self._async_render() == state,
        )

    async def async_update(self):
        """Force update of the state from the template."""
        self.async_check_state()
