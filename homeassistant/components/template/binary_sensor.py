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
    ATTR_EDITABLE,
    CONF_DEVICE_CLASS,
    CONF_ENTITY_ID,
    CONF_ENTITY_PICTURE_TEMPLATE,
    CONF_FRIENDLY_NAME,
    CONF_ICON_TEMPLATE,
    CONF_ID,
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
from homeassistant.helpers.event import async_track_same_state, async_track_state_change
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .common import attach_template_listener, extract_entities, initialise_templates
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

STORAGE_SCHEMA = SENSOR_SCHEMA.extend({vol.Required(CONF_ID): cv.string})

CREATE_FIELDS = {
    vol.Required(CONF_FRIENDLY_NAME): vol.All(str, vol.Length(min=1)),
    vol.Required(CONF_VALUE_TEMPLATE): vol.All(cv.template, vol.Length(min=1)),
    vol.Optional(CONF_ICON_TEMPLATE): cv.template,
    vol.Optional(CONF_ENTITY_PICTURE_TEMPLATE): cv.template,
    vol.Optional(CONF_AVAILABILITY_TEMPLATE): cv.template,
    vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    vol.Optional(CONF_DELAY_ON): vol.All(cv.time_period, cv.positive_timedelta),
    vol.Optional(CONF_DELAY_OFF): vol.All(cv.time_period, cv.positive_timedelta),
    vol.Optional(CONF_ATTRIBUTE_TEMPLATES): vol.Schema({cv.string: cv.template}),
    vol.Optional(CONF_ENTITY_ID): cv.entity_ids,
}

UPDATE_FIELDS = {
    vol.Optional(CONF_FRIENDLY_NAME): cv.string,
    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
    vol.Optional(CONF_ICON_TEMPLATE): cv.template,
    vol.Optional(CONF_ENTITY_PICTURE_TEMPLATE): cv.template,
    vol.Optional(CONF_AVAILABILITY_TEMPLATE): cv.template,
    vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    vol.Optional(CONF_DELAY_ON): vol.All(cv.time_period, cv.positive_timedelta),
    vol.Optional(CONF_DELAY_OFF): vol.All(cv.time_period, cv.positive_timedelta),
    vol.Optional(CONF_ATTRIBUTE_TEMPLATES): vol.Schema({cv.string: cv.template}),
    vol.Optional(CONF_ENTITY_ID): cv.entity_ids,
}


async def async_setup_helpers(hass):
    """Set up the helper storage and WebSockets."""
    storage_collection = BinarySensorStorageCollection(
        Store(hass, STORAGE_VERSION, STORAGE_KEY),
        logging.getLogger(f"{__name__}.storage_collection"),
    )
    collection.attach_entity_component_collection(
        hass.data[DOMAIN],
        storage_collection,
        partial(BinarySensorTemplate.from_storage, hass),
    )
    attach_template_listener(hass, DOMAIN, DOMAIN, storage_collection)

    await storage_collection.async_load()

    collection.StorageCollectionWebsocket(
        storage_collection, f"template/{DOMAIN}", DOMAIN, CREATE_FIELDS, UPDATE_FIELDS
    ).async_setup(hass)

    collection.attach_entity_registry_cleaner(hass, DOMAIN, DOMAIN, storage_collection)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up template binary sensors."""
    yaml_collection = collection.YamlCollection(
        logging.getLogger(f"{__name__}.yaml_collection")
    )

    collection.attach_entity_component_collection(
        hass.data[DOMAIN],
        yaml_collection,
        partial(BinarySensorTemplate.from_config, hass),
    )
    attach_template_listener(hass, DOMAIN, DOMAIN, yaml_collection)

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
        return info[CONF_FRIENDLY_NAME]

    async def _update_data(self, data: dict, update_data: typing.Dict) -> typing.Dict:
        """Return a new updated data object."""
        return {**data, **self.UPDATE_SCHEMA(update_data)}


def init_config(hass, device: str, config: typing.Dict):
    """Initialise templates and entities to be watched."""
    templates = {
        CONF_VALUE_TEMPLATE: config.get(CONF_VALUE_TEMPLATE),
        CONF_ICON_TEMPLATE: config.get(CONF_ICON_TEMPLATE),
        CONF_ENTITY_PICTURE_TEMPLATE: config.get(CONF_ENTITY_PICTURE_TEMPLATE),
        CONF_AVAILABILITY_TEMPLATE: config.get(CONF_AVAILABILITY_TEMPLATE),
    }

    attribute_templates = config.get(CONF_ATTRIBUTE_TEMPLATES, {})

    initialise_templates(hass, templates, attribute_templates)
    config[CONF_ENTITY_ID] = extract_entities(
        device,
        "binary sensor",
        config.get(CONF_ENTITY_ID),
        templates,
        attribute_templates,
    )

    return config


class BinarySensorTemplate(BinarySensorEntity):
    """A virtual binary sensor that triggers from another sensor."""

    def __init__(self, hass: HomeAssistantType, config: ConfigType):
        """Initialize the Template binary sensor."""
        self.hass = hass
        self.editable = False
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, config.get(CONF_ID), hass=hass
        )

        self._config = init_config(hass, self.entity_id, config)
        self._state = None
        self._icon = None
        self._entity_picture = None
        self._available = True
        self._attributes = {}

    @classmethod
    def from_storage(cls, hass, config: typing.Dict) -> "BinarySensorTemplate":
        """Return entity instance initialized from storage."""
        binary_sensor = cls.from_config(hass, config)
        binary_sensor.editable = True
        return binary_sensor

    @classmethod
    def from_config(cls, hass, config: typing.Dict) -> "BinarySensorTemplate":
        """Return entity instance initialized from a config."""
        return cls(hass, STORAGE_SCHEMA(config))

    async def async_added_to_hass(self):
        """Register callbacks."""

        @callback
        def template_bsensor_state_listener(entity, old_state, new_state):
            """Handle the target device state changes."""
            self.async_check_state()

        @callback
        def template_bsensor_startup(event):
            """Update template on startup."""
            if self._config.get(CONF_ENTITY_ID) != MATCH_ALL:
                # Track state change only for valid templates
                async_track_state_change(
                    self.hass,
                    self._config.get(CONF_ENTITY_ID),
                    template_bsensor_state_listener,
                )

            self.async_check_state()

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, template_bsensor_startup
        )

    async def async_update_config(self, config: typing.Dict) -> None:
        """Handle when the config is updated."""
        self._config = init_config(self.hass, config[CONF_ID], config)
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, config.get(CONF_ID), hass=self.hass
        )
        await self.async_update()
        self.async_write_ha_state()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._config.get(CONF_FRIENDLY_NAME)

    @property
    def unique_id(self) -> typing.Optional[str]:
        """Return unique id for the entity."""
        return self._config.get(CONF_ID)

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
        return self._config.get(CONF_DEVICE_CLASS)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {**self._attributes, ATTR_EDITABLE: self.editable}

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
            state = self._config[CONF_VALUE_TEMPLATE].async_render().lower() == "true"
        except TemplateError as ex:
            if ex.args and ex.args[0].startswith(
                "UndefinedError: 'None' has no attribute"
            ):
                # Common during HA startup - so just a warning
                _LOGGER.warning(
                    "Could not render template %s, the state is unknown",
                    self._config.get(CONF_FRIENDLY_NAME),
                )
                return
            _LOGGER.error(
                "Could not render template %s: %s",
                self._config.get(CONF_FRIENDLY_NAME),
                ex,
            )

        for key, value in self._config.get(CONF_ATTRIBUTE_TEMPLATES, {}).items():
            try:
                self._attributes[key] = value.async_render()
            except TemplateError as err:
                _LOGGER.error("Error rendering attribute %s: %s", key, err)

        templates = {
            "_icon": self._config.get(CONF_ICON_TEMPLATE),
            "_entity_picture": self._config.get(CONF_ENTITY_PICTURE_TEMPLATE),
            "_available": self._config.get(CONF_AVAILABILITY_TEMPLATE),
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
                        self._config.get(CONF_FRIENDLY_NAME),
                    )
                else:
                    _LOGGER.error(
                        "Could not render %s template %s: %s",
                        friendly_property_name,
                        self._config.get(CONF_FRIENDLY_NAME),
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
        if (state and not self._config.get(CONF_DELAY_ON)) or (
            not state and not self._config.get(CONF_DELAY_OFF)
        ):
            set_state()
            return

        period = (
            self._config.get(CONF_DELAY_ON)
            if state
            else self._config.get(CONF_DELAY_OFF)
        )
        async_track_same_state(
            self.hass,
            period,
            set_state,
            entity_ids=self._config.get(CONF_ENTITY_ID),
            async_check_same_func=lambda *args: self._async_render() == state,
        )

    async def async_update(self):
        """Force update of the state from the template."""
        self.async_check_state()
