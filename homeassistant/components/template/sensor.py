"""Allows the creation of a sensor that breaks out state_attributes."""

from __future__ import annotations

from datetime import date, datetime
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.sensor import (
    ATTR_LAST_RESET,
    CONF_STATE_CLASS,
    DEVICE_CLASSES_SCHEMA,
    DOMAIN as SENSOR_DOMAIN,
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.components.sensor.helpers import async_parse_date_datetime
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DEVICE_CLASS,
    CONF_DEVICE_ID,
    CONF_ENTITY_PICTURE_TEMPLATE,
    CONF_FRIENDLY_NAME,
    CONF_FRIENDLY_NAME_TEMPLATE,
    CONF_ICON_TEMPLATE,
    CONF_NAME,
    CONF_SENSORS,
    CONF_STATE,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import config_validation as cv, selector, template
from homeassistant.helpers.device import async_device_info_to_link_from_device_id
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.trigger_template_entity import TEMPLATE_SENSOR_BASE_SCHEMA
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from . import TriggerUpdateCoordinator
from .const import (
    CONF_ATTRIBUTE_TEMPLATES,
    CONF_AVAILABILITY_TEMPLATE,
    CONF_OBJECT_ID,
    CONF_TRIGGER,
)
from .template_entity import (
    TEMPLATE_ENTITY_COMMON_SCHEMA,
    TemplateEntity,
    rewrite_common_legacy_to_modern_conf,
)
from .trigger_entity import TriggerEntity

LEGACY_FIELDS = {
    CONF_FRIENDLY_NAME_TEMPLATE: CONF_NAME,
    CONF_FRIENDLY_NAME: CONF_NAME,
    CONF_VALUE_TEMPLATE: CONF_STATE,
}


def validate_last_reset(val):
    """Run extra validation checks."""
    if (
        val.get(ATTR_LAST_RESET) is not None
        and val.get(CONF_STATE_CLASS) != SensorStateClass.TOTAL
    ):
        raise vol.Invalid(
            "last_reset is only valid for template sensors with state_class 'total'"
        )

    return val


SENSOR_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(CONF_STATE): cv.template,
            vol.Optional(ATTR_LAST_RESET): cv.template,
        }
    )
    .extend(TEMPLATE_SENSOR_BASE_SCHEMA.schema)
    .extend(TEMPLATE_ENTITY_COMMON_SCHEMA.schema),
    validate_last_reset,
)


SENSOR_CONFIG_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(CONF_STATE): cv.template,
            vol.Optional(CONF_DEVICE_ID): selector.DeviceSelector(),
        }
    ).extend(TEMPLATE_SENSOR_BASE_SCHEMA.schema),
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
            "You can only add triggers to template entities if they are defined under"
            " `template:`. See the template documentation for more information:"
            " https://www.home-assistant.io/integrations/template/"
        )

    if CONF_SENSORS not in val and SENSOR_DOMAIN not in val:
        raise vol.Invalid(f"Required key {SENSOR_DOMAIN} not defined")

    return val


def rewrite_legacy_to_modern_conf(
    hass: HomeAssistant, cfg: dict[str, dict]
) -> list[dict]:
    """Rewrite legacy sensor definitions to modern ones."""
    sensors = []

    for object_id, entity_cfg in cfg.items():
        entity_cfg = {**entity_cfg, CONF_OBJECT_ID: object_id}

        entity_cfg = rewrite_common_legacy_to_modern_conf(
            hass, entity_cfg, LEGACY_FIELDS
        )

        if CONF_NAME not in entity_cfg:
            entity_cfg[CONF_NAME] = template.Template(object_id, hass)

        sensors.append(entity_cfg)

    return sensors


PLATFORM_SCHEMA = vol.All(
    SENSOR_PLATFORM_SCHEMA.extend(
        {
            vol.Optional(CONF_TRIGGER): cv.match_all,  # to raise custom warning
            vol.Required(CONF_SENSORS): cv.schema_with_slug_keys(LEGACY_SENSOR_SCHEMA),
        }
    ),
    extra_validation_checks,
)

_LOGGER = logging.getLogger(__name__)


@callback
def _async_create_template_tracking_entities(
    async_add_entities: AddEntitiesCallback,
    hass: HomeAssistant,
    definitions: list[dict],
    unique_id_prefix: str | None,
) -> None:
    """Create the template sensors."""
    sensors = []

    for entity_conf in definitions:
        unique_id = entity_conf.get(CONF_UNIQUE_ID)

        if unique_id and unique_id_prefix:
            unique_id = f"{unique_id_prefix}-{unique_id}"

        sensors.append(
            SensorTemplate(
                hass,
                entity_conf,
                unique_id,
            )
        )

    async_add_entities(sensors)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the template sensors."""
    if discovery_info is None:
        _async_create_template_tracking_entities(
            async_add_entities,
            hass,
            rewrite_legacy_to_modern_conf(hass, config[CONF_SENSORS]),
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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize config entry."""
    _options = dict(config_entry.options)
    _options.pop("template_type")
    validated_config = SENSOR_CONFIG_SCHEMA(_options)
    async_add_entities([SensorTemplate(hass, validated_config, config_entry.entry_id)])


@callback
def async_create_preview_sensor(
    hass: HomeAssistant, name: str, config: dict[str, Any]
) -> SensorTemplate:
    """Create a preview sensor."""
    validated_config = SENSOR_CONFIG_SCHEMA(config | {CONF_NAME: name})
    return SensorTemplate(hass, validated_config, None)


class SensorTemplate(TemplateEntity, SensorEntity):
    """Representation of a Template Sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict[str, Any],
        unique_id: str | None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(hass, config=config, fallback_name=None, unique_id=unique_id)
        self._attr_native_unit_of_measurement = config.get(CONF_UNIT_OF_MEASUREMENT)
        self._attr_device_class = config.get(CONF_DEVICE_CLASS)
        self._attr_state_class = config.get(CONF_STATE_CLASS)
        self._template: template.Template = config[CONF_STATE]
        self._attr_last_reset_template: template.Template | None = config.get(
            ATTR_LAST_RESET
        )
        self._attr_device_info = async_device_info_to_link_from_device_id(
            hass,
            config.get(CONF_DEVICE_ID),
        )
        if (object_id := config.get(CONF_OBJECT_ID)) is not None:
            self.entity_id = async_generate_entity_id(
                ENTITY_ID_FORMAT, object_id, hass=hass
            )

    @callback
    def _async_setup_templates(self) -> None:
        """Set up templates."""
        self.add_template_attribute(
            "_attr_native_value", self._template, None, self._update_state
        )
        if self._attr_last_reset_template is not None:
            self.add_template_attribute(
                "_attr_last_reset",
                self._attr_last_reset_template,
                cv.datetime,
                self._update_last_reset,
            )

        super()._async_setup_templates()

    @callback
    def _update_last_reset(self, result):
        self._attr_last_reset = result

    @callback
    def _update_state(self, result):
        super()._update_state(result)
        if isinstance(result, TemplateError):
            self._attr_native_value = None
            return

        if result is None or self.device_class not in (
            SensorDeviceClass.DATE,
            SensorDeviceClass.TIMESTAMP,
        ):
            self._attr_native_value = result
            return

        self._attr_native_value = async_parse_date_datetime(
            result, self.entity_id, self.device_class
        )


class TriggerSensorEntity(TriggerEntity, RestoreSensor):
    """Sensor entity based on trigger data."""

    domain = SENSOR_DOMAIN
    extra_template_keys = (CONF_STATE,)

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: TriggerUpdateCoordinator,
        config: ConfigType,
    ) -> None:
        """Initialize."""
        super().__init__(hass, coordinator, config)

        if (last_reset_template := config.get(ATTR_LAST_RESET)) is not None:
            if last_reset_template.is_static:
                self._static_rendered[ATTR_LAST_RESET] = last_reset_template.template
            else:
                self._to_render_simple.append(ATTR_LAST_RESET)

        self._attr_state_class = config.get(CONF_STATE_CLASS)
        self._attr_native_unit_of_measurement = config.get(CONF_UNIT_OF_MEASUREMENT)

    async def async_added_to_hass(self) -> None:
        """Restore last state."""
        await super().async_added_to_hass()
        if (
            (last_state := await self.async_get_last_state()) is not None
            and (extra_data := await self.async_get_last_sensor_data()) is not None
            and last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
            # The trigger might have fired already while we waited for stored data,
            # then we should not restore state
            and CONF_STATE not in self._rendered
        ):
            self._rendered[CONF_STATE] = extra_data.native_value
            self.restore_attributes(last_state)

    @property
    def native_value(self) -> str | datetime | date | None:
        """Return state of the sensor."""
        return self._rendered.get(CONF_STATE)

    @callback
    def _process_data(self) -> None:
        """Process new data."""
        super()._process_data()

        # Update last_reset
        if ATTR_LAST_RESET in self._rendered:
            parsed_timestamp = dt_util.parse_datetime(self._rendered[ATTR_LAST_RESET])
            if parsed_timestamp is None:
                _LOGGER.warning(
                    "%s rendered invalid timestamp for last_reset attribute: %s",
                    self.entity_id,
                    self._rendered.get(ATTR_LAST_RESET),
                )
            else:
                self._attr_last_reset = parsed_timestamp

        if (
            state := self._rendered.get(CONF_STATE)
        ) is None or self.device_class not in (
            SensorDeviceClass.DATE,
            SensorDeviceClass.TIMESTAMP,
        ):
            return

        self._rendered[CONF_STATE] = async_parse_date_datetime(
            state, self.entity_id, self.device_class
        )
