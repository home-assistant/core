"""Support for RESTful API sensors."""

import logging
from typing import Any, override
from xml.parsers.expat import ExpatError

import voluptuous as vol

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
)
from homeassistant.const import (
    CONF_FORCE_UPDATE,
    CONF_RESOURCE,
    CONF_RESOURCE_TEMPLATE,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.trigger_template_entity import (
    ManualTriggerSensorEntity,
    ValueTemplate,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_JSON_ATTRS, CONF_JSON_ATTRS_PATH, DEFAULT_SENSOR_NAME
from .data import RestData
from .entity import (
    RestEntity,
    async_get_config_rest_data_and_coordinator,
    async_get_trigger_entity_config,
)
from .schema import RESOURCE_SCHEMA, SENSOR_SCHEMA
from .util import parse_json_attributes

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = vol.All(
    SENSOR_PLATFORM_SCHEMA.extend({**RESOURCE_SCHEMA, **SENSOR_SCHEMA}),
    cv.has_at_least_one_key(CONF_RESOURCE, CONF_RESOURCE_TEMPLATE),
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the RESTful sensor."""
    conf, rest, coordinator = await async_get_config_rest_data_and_coordinator(
        hass, config, SENSOR_DOMAIN, discovery_info
    )
    trigger_entity_config = async_get_trigger_entity_config(
        hass, conf, DEFAULT_SENSOR_NAME
    )
    async_add_entities(
        [
            RestSensor(
                hass,
                coordinator,
                rest,
                conf,
                trigger_entity_config,
            )
        ],
    )


class RestSensor(ManualTriggerSensorEntity, RestEntity):
    """Implementation of a REST sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: DataUpdateCoordinator[None] | None,
        rest: RestData,
        config: ConfigType,
        trigger_entity_config: ConfigType,
    ) -> None:
        """Initialize the REST sensor."""
        ManualTriggerSensorEntity.__init__(self, hass, trigger_entity_config)
        RestEntity.__init__(
            self,
            coordinator,
            rest,
            config.get(CONF_RESOURCE_TEMPLATE),
            config[CONF_FORCE_UPDATE],
        )
        self._value_template: ValueTemplate | None = config.get(CONF_VALUE_TEMPLATE)
        self._json_attrs = config.get(CONF_JSON_ATTRS)
        self._json_attrs_path = config.get(CONF_JSON_ATTRS_PATH)
        self._attr_extra_state_attributes = {}

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        available1 = RestEntity.available.fget(self)  # type: ignore[attr-defined]
        available2 = ManualTriggerSensorEntity.available.fget(self)  # type: ignore[attr-defined]
        return bool(available1 and available2)

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        return dict(self._attr_extra_state_attributes)

    @override
    def _update_from_rest_data(self) -> None:
        """Update state from the rest data."""
        try:
            value = self.rest.data_without_xml()
        except ExpatError as err:
            _LOGGER.warning(
                "REST xml result could not be parsed and converted to JSON: %s", err
            )
            value = self.rest.data

        variables = self._template_variables_with_value(value)
        if not self._render_availability_template(variables):
            self.async_write_ha_state()
            return

        if self._json_attrs:
            self._attr_extra_state_attributes = parse_json_attributes(
                value, self._json_attrs, self._json_attrs_path
            )

        if value is not None and self._value_template is not None:
            value = self._value_template.async_render_as_value_template(
                self.entity_id, variables, None
            )

        self._set_native_value_with_possible_timestamp(value)
        self._process_manual_data(variables)
        self.async_write_ha_state()
