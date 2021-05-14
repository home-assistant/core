"""Allows the creation of a sensor that breaks out state_attributes."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.sensor import (
    DEVICE_CLASSES_SCHEMA,
    DOMAIN as SENSOR_DOMAIN,
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
    CONF_ICON,
    CONF_ICON_TEMPLATE,
    CONF_NAME,
    CONF_SENSORS,
    CONF_STATE,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import config_validation as cv, template
from homeassistant.helpers.entity import async_generate_entity_id

from .const import (
    CONF_ATTRIBUTE_TEMPLATES,
    CONF_ATTRIBUTES,
    CONF_AVAILABILITY,
    CONF_AVAILABILITY_TEMPLATE,
    CONF_OBJECT_ID,
    CONF_PICTURE,
    CONF_TRIGGER,
)
from .template_entity import TemplateEntity
from .trigger_entity import TriggerEntity

LEGACY_FIELDS = {
    CONF_ICON_TEMPLATE: CONF_ICON,
    CONF_ENTITY_PICTURE_TEMPLATE: CONF_PICTURE,
    CONF_AVAILABILITY_TEMPLATE: CONF_AVAILABILITY,
    CONF_ATTRIBUTE_TEMPLATES: CONF_ATTRIBUTES,
    CONF_FRIENDLY_NAME_TEMPLATE: CONF_NAME,
    CONF_FRIENDLY_NAME: CONF_NAME,
    CONF_VALUE_TEMPLATE: CONF_STATE,
}


SENSOR_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME): cv.template,
        vol.Required(CONF_STATE): cv.template,
        vol.Optional(CONF_ICON): cv.template,
        vol.Optional(CONF_PICTURE): cv.template,
        vol.Optional(CONF_AVAILABILITY): cv.template,
        vol.Optional(CONF_ATTRIBUTES): vol.Schema({cv.string: cv.template}),
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)


LEGACY_SENSOR_SCHEMA = vol.All(
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


def extra_validation_checks(val):
    """Run extra validation checks."""
    if CONF_TRIGGER in val:
        raise vol.Invalid(
            "You can only add triggers to template entities if they are defined under `template:`. "
            "See the template documentation for more information: https://www.home-assistant.io/integrations/template/"
        )

    if CONF_SENSORS not in val and SENSOR_DOMAIN not in val:
        raise vol.Invalid(f"Required key {SENSOR_DOMAIN} not defined")

    return val


def rewrite_legacy_to_modern_conf(cfg: dict[str, dict]) -> list[dict]:
    """Rewrite a legacy sensor definitions to modern ones."""
    sensors = []

    for object_id, entity_cfg in cfg.items():
        entity_cfg = {**entity_cfg, CONF_OBJECT_ID: object_id}

        for from_key, to_key in LEGACY_FIELDS.items():
            if from_key not in entity_cfg or to_key in entity_cfg:
                continue

            val = entity_cfg.pop(from_key)
            if isinstance(val, str):
                val = template.Template(val)
            entity_cfg[to_key] = val

        if CONF_NAME not in entity_cfg:
            entity_cfg[CONF_NAME] = template.Template(object_id)

        sensors.append(entity_cfg)

    return sensors


PLATFORM_SCHEMA = vol.All(
    PLATFORM_SCHEMA.extend(
        {
            vol.Optional(CONF_TRIGGER): cv.match_all,  # to raise custom warning
            vol.Required(CONF_SENSORS): cv.schema_with_slug_keys(LEGACY_SENSOR_SCHEMA),
        }
    ),
    extra_validation_checks,
)


@callback
def _async_create_template_tracking_entities(
    async_add_entities, hass, definitions: list[dict], unique_id_prefix: str | None
):
    """Create the template sensors."""
    sensors = []

    for entity_conf in definitions:
        # Still available on legacy
        object_id = entity_conf.get(CONF_OBJECT_ID)

        state_template = entity_conf[CONF_STATE]
        icon_template = entity_conf.get(CONF_ICON)
        entity_picture_template = entity_conf.get(CONF_PICTURE)
        availability_template = entity_conf.get(CONF_AVAILABILITY)
        friendly_name_template = entity_conf.get(CONF_NAME)
        unit_of_measurement = entity_conf.get(CONF_UNIT_OF_MEASUREMENT)
        device_class = entity_conf.get(CONF_DEVICE_CLASS)
        attribute_templates = entity_conf.get(CONF_ATTRIBUTES, {})
        unique_id = entity_conf.get(CONF_UNIQUE_ID)

        if unique_id and unique_id_prefix:
            unique_id = f"{unique_id_prefix}-{unique_id}"

        sensors.append(
            SensorTemplate(
                hass,
                object_id,
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

    async_add_entities(sensors)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the template sensors."""
    if discovery_info is None:
        _async_create_template_tracking_entities(
            async_add_entities,
            hass,
            rewrite_legacy_to_modern_conf(config[CONF_SENSORS]),
            None,
        )
        return

    if "coordinator" in discovery_info:
        async_add_entities(
            TriggerSensorEntity(hass, discovery_info["coordinator"], config)
            for config in discovery_info["entities"]
        )
        return

    _async_create_template_tracking_entities(
        async_add_entities,
        hass,
        discovery_info["entities"],
        discovery_info["unique_id"],
    )


class SensorTemplate(TemplateEntity, SensorEntity):
    """Representation of a Template Sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        object_id: str | None,
        friendly_name_template: template.Template | None,
        unit_of_measurement: str | None,
        state_template: template.Template,
        icon_template: template.Template | None,
        entity_picture_template: template.Template | None,
        availability_template: template.Template | None,
        device_class: str | None,
        attribute_templates: dict[str, template.Template],
        unique_id: str | None,
    ):
        """Initialize the sensor."""
        super().__init__(
            attribute_templates=attribute_templates,
            availability_template=availability_template,
            icon_template=icon_template,
            entity_picture_template=entity_picture_template,
        )
        if object_id is not None:
            self.entity_id = async_generate_entity_id(
                ENTITY_ID_FORMAT, object_id, hass=hass
            )

        self._name: str | None = None
        self._friendly_name_template = friendly_name_template

        # Try to render the name as it can influence the entity ID
        if friendly_name_template:
            friendly_name_template.hass = hass
            try:
                self._name = friendly_name_template.async_render(parse_result=False)
            except template.TemplateError:
                pass

        self._unit_of_measurement = unit_of_measurement
        self._template = state_template
        self._state = None
        self._device_class = device_class

        self._unique_id = unique_id

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.add_template_attribute("_state", self._template, None, self._update_state)
        if self._friendly_name_template and not self._friendly_name_template.is_static:
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

    domain = SENSOR_DOMAIN
    extra_template_keys = (CONF_STATE,)

    @property
    def state(self) -> str | None:
        """Return state of the sensor."""
        return self._rendered.get(CONF_STATE)
