"""Allows the creation of a sensor that breaks out state_attributes."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.sensor import (
    DEVICE_CLASSES_SCHEMA,
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DEVICE_CLASS,
    CONF_ENTITY_PICTURE_TEMPLATE,
    CONF_FRIENDLY_NAME,
    CONF_FRIENDLY_NAME_TEMPLATE,
    CONF_ICON_TEMPLATE,
    CONF_SENSORS,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id

from .const import CONF_ATTRIBUTE_TEMPLATES, CONF_AVAILABILITY_TEMPLATE, CONF_TRIGGER
from .template_entity import TemplateEntity
from .trigger_entity import TriggerEntity

SENSOR_SCHEMA = vol.All(
    cv.deprecated(ATTR_ENTITY_ID),
    vol.Schema(
        {
            vol.Required(CONF_VALUE_TEMPLATE): cv.template,
            vol.Optional(CONF_ICON_TEMPLATE): cv.template,
            vol.Optional(CONF_ENTITY_PICTURE_TEMPLATE): cv.template,
            vol.Optional(CONF_FRIENDLY_NAME_TEMPLATE): cv.template,
            vol.Optional(CONF_AVAILABILITY_TEMPLATE): cv.template,
            vol.Optional(CONF_ATTRIBUTE_TEMPLATES, default={}): vol.Schema(
                {cv.string: cv.template}
            ),
            vol.Optional(CONF_FRIENDLY_NAME): cv.string,
            vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
            vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
            vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
            vol.Optional(CONF_UNIQUE_ID): cv.string,
        }
    ),
)


def trigger_warning(val):
    """Warn if a trigger is defined."""
    if CONF_TRIGGER in val:
        raise vol.Invalid(
            "You can only add triggers to template entities if they are defined under `template:`. "
            "See the template documentation for more information: https://www.home-assistant.io/integrations/template/"
        )

    return val


PLATFORM_SCHEMA = vol.All(
    PLATFORM_SCHEMA.extend(
        {
            vol.Optional(CONF_TRIGGER): cv.match_all,  # to raise custom warning
            vol.Required(CONF_SENSORS): cv.schema_with_slug_keys(SENSOR_SCHEMA),
        }
    ),
    trigger_warning,
)


@callback
def _async_create_template_tracking_entities(hass, config):
    """Create the template sensors."""
    sensors = []

    for device, device_config in config[CONF_SENSORS].items():
        state_template = device_config[CONF_VALUE_TEMPLATE]
        icon_template = device_config.get(CONF_ICON_TEMPLATE)
        entity_picture_template = device_config.get(CONF_ENTITY_PICTURE_TEMPLATE)
        availability_template = device_config.get(CONF_AVAILABILITY_TEMPLATE)
        friendly_name = device_config.get(CONF_FRIENDLY_NAME, device)
        friendly_name_template = device_config.get(CONF_FRIENDLY_NAME_TEMPLATE)
        unit_of_measurement = device_config.get(CONF_UNIT_OF_MEASUREMENT)
        device_class = device_config.get(CONF_DEVICE_CLASS)
        attribute_templates = device_config[CONF_ATTRIBUTE_TEMPLATES]
        unique_id = device_config.get(CONF_UNIQUE_ID)

        sensors.append(
            SensorTemplate(
                hass,
                device,
                friendly_name,
                friendly_name_template,
                unit_of_measurement,
                state_template,
                icon_template,
                entity_picture_template,
                availability_template,
                device_class,
                attribute_templates,
                unique_id,
            )
        )

    return sensors


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the template sensors."""
    if discovery_info is None:
        async_add_entities(_async_create_template_tracking_entities(hass, config))
    else:
        async_add_entities(
            TriggerSensorEntity(hass, discovery_info["coordinator"], device_id, config)
            for device_id, config in discovery_info["entities"].items()
        )


class SensorTemplate(TemplateEntity, SensorEntity):
    """Representation of a Template Sensor."""

    def __init__(
        self,
        hass,
        device_id,
        friendly_name,
        friendly_name_template,
        unit_of_measurement,
        state_template,
        icon_template,
        entity_picture_template,
        availability_template,
        device_class,
        attribute_templates,
        unique_id,
    ):
        """Initialize the sensor."""
        super().__init__(
            attribute_templates=attribute_templates,
            availability_template=availability_template,
            icon_template=icon_template,
            entity_picture_template=entity_picture_template,
        )
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, device_id, hass=hass
        )
        self._name = friendly_name
        self._friendly_name_template = friendly_name_template
        self._unit_of_measurement = unit_of_measurement
        self._template = state_template
        self._state = None
        self._device_class = device_class

        self._unique_id = unique_id

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.add_template_attribute("_state", self._template, None, self._update_state)
        if self._friendly_name_template is not None:
            self.add_template_attribute("_name", self._friendly_name_template)

        await super().async_added_to_hass()

    @callback
    def _update_state(self, result):
        super()._update_state(result)
        self._state = None if isinstance(result, TemplateError) else result

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id of this sensor."""
        return self._unique_id

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_class(self) -> str | None:
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def unit_of_measurement(self):
        """Return the unit_of_measurement of the device."""
        return self._unit_of_measurement


class TriggerSensorEntity(TriggerEntity, SensorEntity):
    """Sensor entity based on trigger data."""

    extra_template_keys = (CONF_VALUE_TEMPLATE,)

    @property
    def state(self) -> str | None:
        """Return state of the sensor."""
        return self._rendered.get(CONF_VALUE_TEMPLATE)
