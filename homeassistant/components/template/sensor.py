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
    STATE_CLASSES_SCHEMA,
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
    CONF_ENTITY_PICTURE_TEMPLATE,
    CONF_FRIENDLY_NAME,
    CONF_FRIENDLY_NAME_TEMPLATE,
    CONF_ICON_TEMPLATE,
    CONF_NAME,
    CONF_SENSORS,
    CONF_STATE,
    CONF_TRIGGER,
    CONF_TRIGGERS,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import config_validation as cv, template
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from . import TriggerUpdateCoordinator
from .helpers import (
    async_setup_template_entry,
    async_setup_template_platform,
    async_setup_template_preview,
)
from .schemas import (
    TEMPLATE_ENTITY_ATTRIBUTES_SCHEMA_LEGACY,
    TEMPLATE_ENTITY_AVAILABILITY_SCHEMA_LEGACY,
    TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA,
    make_template_entity_common_modern_attributes_schema,
)
from .template_entity import TemplateEntity
from .trigger_entity import TriggerEntity

DEFAULT_NAME = "Template Sensor"

LEGACY_FIELDS = {
    CONF_FRIENDLY_NAME_TEMPLATE: CONF_NAME,
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


SENSOR_COMMON_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_STATE): cv.template,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_STATE_CLASS): STATE_CLASSES_SCHEMA,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    }
)

SENSOR_YAML_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Optional(ATTR_LAST_RESET): cv.template,
        }
    )
    .extend(SENSOR_COMMON_SCHEMA.schema)
    .extend(
        make_template_entity_common_modern_attributes_schema(
            SENSOR_DOMAIN, DEFAULT_NAME
        ).schema
    ),
    validate_last_reset,
)

SENSOR_CONFIG_ENTRY_SCHEMA = SENSOR_COMMON_SCHEMA.extend(
    TEMPLATE_ENTITY_COMMON_CONFIG_ENTRY_SCHEMA.schema
)

SENSOR_LEGACY_YAML_SCHEMA = vol.All(
    cv.deprecated(ATTR_ENTITY_ID),
    vol.Schema(
        {
            vol.Required(CONF_VALUE_TEMPLATE): cv.template,
            vol.Optional(CONF_ICON_TEMPLATE): cv.template,
            vol.Optional(CONF_ENTITY_PICTURE_TEMPLATE): cv.template,
            vol.Optional(CONF_FRIENDLY_NAME_TEMPLATE): cv.template,
            vol.Optional(CONF_FRIENDLY_NAME): cv.string,
            vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
            vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
            vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
            vol.Optional(CONF_UNIQUE_ID): cv.string,
        }
    )
    .extend(TEMPLATE_ENTITY_ATTRIBUTES_SCHEMA_LEGACY.schema)
    .extend(TEMPLATE_ENTITY_AVAILABILITY_SCHEMA_LEGACY.schema),
)


def extra_validation_checks(val):
    """Run extra validation checks."""
    if CONF_TRIGGERS in val or CONF_TRIGGER in val:
        raise vol.Invalid(
            "You can only add triggers to template entities if they are defined under"
            " `template:`. See the template documentation for more information:"
            " https://www.home-assistant.io/integrations/template/"
        )

    if CONF_SENSORS not in val and SENSOR_DOMAIN not in val:
        raise vol.Invalid(f"Required key {SENSOR_DOMAIN} not defined")

    return val


PLATFORM_SCHEMA = vol.All(
    SENSOR_PLATFORM_SCHEMA.extend(
        {
            vol.Optional(CONF_TRIGGER): cv.match_all,  # to raise custom warning
            vol.Optional(CONF_TRIGGERS): cv.match_all,  # to raise custom warning
            vol.Required(CONF_SENSORS): cv.schema_with_slug_keys(
                SENSOR_LEGACY_YAML_SCHEMA
            ),
        }
    ),
    extra_validation_checks,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the template sensors."""
    await async_setup_template_platform(
        hass,
        SENSOR_DOMAIN,
        config,
        StateSensorEntity,
        TriggerSensorEntity,
        async_add_entities,
        discovery_info,
        LEGACY_FIELDS,
        legacy_key=CONF_SENSORS,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize config entry."""
    await async_setup_template_entry(
        hass,
        config_entry,
        async_add_entities,
        StateSensorEntity,
        SENSOR_CONFIG_ENTRY_SCHEMA,
    )


@callback
def async_create_preview_sensor(
    hass: HomeAssistant, name: str, config: dict[str, Any]
) -> StateSensorEntity:
    """Create a preview sensor."""
    return async_setup_template_preview(
        hass, name, config, StateSensorEntity, SENSOR_CONFIG_ENTRY_SCHEMA
    )


class StateSensorEntity(TemplateEntity, SensorEntity):
    """Representation of a Template Sensor."""

    _attr_should_poll = False
    _entity_id_format = ENTITY_ID_FORMAT

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict[str, Any],
        unique_id: str | None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(hass, config, unique_id)
        self._attr_native_unit_of_measurement = config.get(CONF_UNIT_OF_MEASUREMENT)
        self._attr_device_class = config.get(CONF_DEVICE_CLASS)
        self._attr_state_class = config.get(CONF_STATE_CLASS)
        self._template: template.Template = config[CONF_STATE]
        self._attr_last_reset_template: template.Template | None = config.get(
            ATTR_LAST_RESET
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

    _entity_id_format = ENTITY_ID_FORMAT
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

        self._parse_result.add(CONF_STATE)
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
