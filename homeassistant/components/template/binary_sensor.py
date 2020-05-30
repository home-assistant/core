"""Support for exposing a templated binary sensor."""
from functools import partial
import logging
import typing

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA,
    DOMAIN,
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_ENTITY_ID,
    CONF_ENTITY_PICTURE_TEMPLATE,
    CONF_FRIENDLY_NAME,
    CONF_ICON_TEMPLATE,
    CONF_ID,
    CONF_NAME,
    CONF_SENSORS,
    CONF_VALUE_TEMPLATE,
    EVENT_HOMEASSISTANT_START,
    MATCH_ALL,
)
from homeassistant.core import callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import collection
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.event import async_track_same_state, async_track_state_change
from homeassistant.helpers.storage import Store

from .common import extract_entities, initialise_templates, register_component
from .const import CONF_AVAILABILITY_TEMPLATE

_LOGGER = logging.getLogger(__name__)

CONF_DELAY_ON = "delay_on"
CONF_DELAY_OFF = "delay_off"
CONF_ATTRIBUTE_TEMPLATES = "attribute_templates"
STORAGE_KEY = f"template.{DOMAIN}"
STORAGE_VERSION = 1

SENSOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_ICON_TEMPLATE): cv.template,
        vol.Optional(CONF_ENTITY_PICTURE_TEMPLATE): cv.template,
        vol.Optional(CONF_AVAILABILITY_TEMPLATE): cv.template,
        vol.Optional(CONF_ATTRIBUTE_TEMPLATES): vol.Schema({cv.string: cv.template}),
        vol.Optional(CONF_FRIENDLY_NAME): cv.string,
        vol.Optional(CONF_ENTITY_ID): cv.entity_ids,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_DELAY_ON): vol.All(cv.time_period, cv.positive_timedelta),
        vol.Optional(CONF_DELAY_OFF): vol.All(cv.time_period, cv.positive_timedelta),
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_SENSORS): cv.schema_with_slug_keys(SENSOR_SCHEMA)}
)

CREATE_FIELDS = {
    vol.Required(CONF_FRIENDLY_NAME): vol.All(str, vol.Length(min=1)),
    vol.Required(CONF_VALUE_TEMPLATE): vol.All(str, vol.Length(min=1)),
    vol.Optional(CONF_ICON_TEMPLATE): str,
    vol.Optional(CONF_ENTITY_PICTURE_TEMPLATE): str,
    vol.Optional(CONF_AVAILABILITY_TEMPLATE): str,
    vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    vol.Optional(CONF_DELAY_ON): vol.All(cv.time_period, cv.positive_timedelta),
    vol.Optional(CONF_DELAY_OFF): vol.All(cv.time_period, cv.positive_timedelta),
    vol.Optional(CONF_ATTRIBUTE_TEMPLATES): vol.Schema({cv.string: str}),
    vol.Optional(CONF_ENTITY_ID): cv.entity_ids,
}

UPDATE_FIELDS = {
    vol.Optional(CONF_FRIENDLY_NAME): cv.string,
    vol.Optional(CONF_VALUE_TEMPLATE): str,
    vol.Optional(CONF_ICON_TEMPLATE): str,
    vol.Optional(CONF_ENTITY_PICTURE_TEMPLATE): str,
    vol.Optional(CONF_AVAILABILITY_TEMPLATE): str,
    vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    vol.Optional(CONF_DELAY_ON): vol.All(cv.time_period, cv.positive_timedelta),
    vol.Optional(CONF_DELAY_OFF): vol.All(cv.time_period, cv.positive_timedelta),
    vol.Optional(CONF_ATTRIBUTE_TEMPLATES): vol.Schema({cv.string: str}),
    vol.Optional(CONF_ENTITY_ID): cv.entity_ids,
}

CONVERT_TEMPLATE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_ICON_TEMPLATE): cv.template,
        vol.Optional(CONF_ENTITY_PICTURE_TEMPLATE): cv.template,
        vol.Optional(CONF_AVAILABILITY_TEMPLATE): cv.template,
        vol.Optional(CONF_ATTRIBUTE_TEMPLATES): vol.Schema({cv.string: cv.template}),
    },
    extra=True,
)


def getComponent(hass):
    """Get the EntityComponent for this platform."""
    if STORAGE_KEY not in hass.data:
        component = EntityComponent(_LOGGER, DOMAIN, hass)
        register_component(component)
        hass.data[STORAGE_KEY] = component

    return hass.data[STORAGE_KEY]


async def async_setup_helpers(hass):
    """Set up the helper storage and WebSockets."""
    component = getComponent(hass)

    storage_collection = BinarySensorStorageCollection(
        Store(hass, STORAGE_VERSION, STORAGE_KEY),
        logging.getLogger(f"{__name__}.storage_collection"),
    )
    collection.attach_entity_component_collection(
        component, storage_collection, partial(BinarySensorTemplate.from_storage, hass)
    )

    await storage_collection.async_load()

    collection.StorageCollectionWebsocket(
        storage_collection, f"template/{DOMAIN}", DOMAIN, CREATE_FIELDS, UPDATE_FIELDS
    ).async_setup(hass)

    collection.attach_entity_registry_cleaner(hass, DOMAIN, DOMAIN, storage_collection)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up template binary sensors."""
    component = getComponent(hass)

    yaml_collection = collection.YamlCollection(
        logging.getLogger(f"{__name__}.yaml_collection")
    )

    collection.attach_entity_component_collection(
        component, yaml_collection, partial(BinarySensorTemplate.from_storage, hass)
    )

    await yaml_collection.async_load(
        [{CONF_ID: id_, **cfg} for id_, cfg in config.get(CONF_SENSORS, {}).items()]
    )

    collection.attach_entity_registry_cleaner(hass, DOMAIN, DOMAIN, yaml_collection)


class BinarySensorStorageCollection(collection.StorageCollection):
    """Input storage based collection."""

    CREATE_SCHEMA = vol.Schema(CREATE_FIELDS)
    UPDATE_SCHEMA = vol.Schema(UPDATE_FIELDS)

    async def _process_create_data(self, data: typing.Dict) -> typing.Dict:
        """Validate the config is valid."""
        return self.CREATE_SCHEMA(data)

    @callback
    def _get_suggested_id(self, info: typing.Dict) -> str:
        """Suggest an ID based on the config."""
        return info[CONF_NAME]

    async def _update_data(self, data: dict, update_data: typing.Dict) -> typing.Dict:
        """Return a new updated data object."""
        return self.UPDATE_SCHEMA({**data, **update_data})


class BinarySensorTemplate(BinarySensorEntity):
    """A virtual binary sensor that triggers from another sensor."""

    def __init__(
        self,
        hass,
        id_=None,
        friendly_name=None,
        device_class=None,
        value_template=None,
        icon_template=None,
        entity_picture_template=None,
        availability_template=None,
        entity_id=None,
        delay_on=None,
        delay_off=None,
        attribute_templates={},
    ):
        """Initialize the Template binary sensor."""
        self.hass = hass
        self._id = id_
        self.entity_id = async_generate_entity_id(ENTITY_ID_FORMAT, id_, hass=hass)
        self._name = friendly_name
        self._device_class = device_class
        self._template = value_template
        self._state = None
        self._icon_template = icon_template
        self._availability_template = availability_template
        self._entity_picture_template = entity_picture_template
        self._icon = None
        self._entity_picture = None
        self._entities = entity_id
        self._delay_on = delay_on
        self._delay_off = delay_off
        self._available = True
        self._attribute_templates = attribute_templates
        self._attributes = {}

    @classmethod
    def from_storage(cls, hass, config: typing.Dict) -> "BinarySensorTemplate":
        """Return entity instance initialized from yaml storage."""
        config = CONVERT_TEMPLATE_SCHEMA(config)  # Converts strings to templates

        templates = {
            CONF_VALUE_TEMPLATE: config.get(CONF_VALUE_TEMPLATE),
            CONF_ICON_TEMPLATE: config.get(CONF_ICON_TEMPLATE),
            CONF_ENTITY_PICTURE_TEMPLATE: config.get(CONF_ENTITY_PICTURE_TEMPLATE),
            CONF_AVAILABILITY_TEMPLATE: config.get(CONF_AVAILABILITY_TEMPLATE),
        }

        attribute_templates = config.get(CONF_ATTRIBUTE_TEMPLATES, {})

        initialise_templates(hass, templates, attribute_templates)
        config[CONF_ENTITY_ID] = extract_entities(
            config[CONF_ID],
            "binary sensor",
            config.get(CONF_ENTITY_ID),
            templates,
            attribute_templates,
        )

        # Don't override builtin id function
        config["id_"] = config.pop(CONF_ID)

        return cls(hass, **config)

    async def async_added_to_hass(self):
        """Register callbacks."""

        @callback
        def template_bsensor_state_listener(entity, old_state, new_state):
            """Handle the target device state changes."""
            self.async_check_state()

        @callback
        def template_bsensor_startup(event):
            """Update template on startup."""
            if self._entities != MATCH_ALL:
                # Track state change only for valid templates
                async_track_state_change(
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
    def unique_id(self) -> typing.Optional[str]:
        """Return unique id for the entity."""
        return self._id

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
                        "Could not render %s template %s, the state is unknown.",
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
