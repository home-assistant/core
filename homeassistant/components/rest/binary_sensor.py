"""Support for RESTful binary sensors."""

import logging
from typing import override
from xml.parsers.expat import ExpatError

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    PLATFORM_SCHEMA as BINARY_SENSOR_PLATFORM_SCHEMA,
    BinarySensorEntity,
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
    ManualTriggerEntity,
    ValueTemplate,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DEFAULT_BINARY_SENSOR_NAME
from .data import RestData
from .entity import (
    RestEntity,
    async_get_config_rest_data_and_coordinator,
    async_get_trigger_entity_config,
)
from .schema import BINARY_SENSOR_SCHEMA, RESOURCE_SCHEMA

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = vol.All(
    BINARY_SENSOR_PLATFORM_SCHEMA.extend({**RESOURCE_SCHEMA, **BINARY_SENSOR_SCHEMA}),
    cv.has_at_least_one_key(CONF_RESOURCE, CONF_RESOURCE_TEMPLATE),
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the REST binary sensor."""

    conf, rest, coordinator = await async_get_config_rest_data_and_coordinator(
        hass, config, BINARY_SENSOR_DOMAIN, discovery_info
    )
    trigger_entity_config = async_get_trigger_entity_config(
        hass, conf, DEFAULT_BINARY_SENSOR_NAME
    )

    async_add_entities(
        [
            RestBinarySensor(
                hass,
                coordinator,
                rest,
                conf,
                trigger_entity_config,
            )
        ],
    )


class RestBinarySensor(ManualTriggerEntity, RestEntity, BinarySensorEntity):
    """Representation of a REST binary sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: DataUpdateCoordinator[None] | None,
        rest: RestData,
        config: ConfigType,
        trigger_entity_config: ConfigType,
    ) -> None:
        """Initialize a REST binary sensor."""
        ManualTriggerEntity.__init__(self, hass, trigger_entity_config)
        RestEntity.__init__(
            self,
            coordinator,
            rest,
            config.get(CONF_RESOURCE_TEMPLATE),
            config[CONF_FORCE_UPDATE],
        )
        self._previous_data = None
        self._value_template: ValueTemplate | None = config.get(CONF_VALUE_TEMPLATE)

    @property
    @override
    def available(self) -> bool:
        """Return if entity is available."""
        available1 = RestEntity.available.fget(self)  # type: ignore[attr-defined]
        available2 = ManualTriggerEntity.available.fget(self)  # type: ignore[attr-defined]
        return bool(available1 and available2)

    @override
    def _update_from_rest_data(self) -> None:
        """Update state from the rest data."""
        if self.rest.data is None:
            self._attr_is_on = False
            return

        try:
            response = self.rest.data_without_xml()
        except ExpatError as err:
            self._attr_is_on = False
            _LOGGER.warning(
                "REST xml result could not be parsed and converted to JSON: %s", err
            )
            return

        variables = self._template_variables_with_value(response)
        if not self._render_availability_template(variables):
            self.async_write_ha_state()
            return

        if response is not None and self._value_template is not None:
            response = self._value_template.async_render_as_value_template(
                self.entity_id, variables, False
            )

        try:
            self._attr_is_on = bool(int(str(response)))
        except ValueError:
            self._attr_is_on = {
                "true": True,
                "on": True,
                "open": True,
                "yes": True,
            }.get(str(response).lower(), False)

        self._process_manual_data(variables)
        self.async_write_ha_state()
