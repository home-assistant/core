"""Support for RESTful binary sensors."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    PLATFORM_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_FORCE_UPDATE,
    CONF_RESOURCE,
    CONF_RESOURCE_TEMPLATE,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.template_entity import TemplateEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import async_get_config_and_coordinator, create_rest_data_from_config
from .const import DEFAULT_BINARY_SENSOR_NAME
from .entity import RestEntity
from .schema import BINARY_SENSOR_SCHEMA, RESOURCE_SCHEMA

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({**RESOURCE_SCHEMA, **BINARY_SENSOR_SCHEMA})

PLATFORM_SCHEMA = vol.All(
    cv.has_at_least_one_key(CONF_RESOURCE, CONF_RESOURCE_TEMPLATE), PLATFORM_SCHEMA
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the REST binary sensor."""
    # Must update the sensor now (including fetching the rest resource) to
    # ensure it's updating its state.
    if discovery_info is not None:
        conf, coordinator, rest = await async_get_config_and_coordinator(
            hass, BINARY_SENSOR_DOMAIN, discovery_info
        )
    else:
        conf = config
        coordinator = None
        rest = create_rest_data_from_config(hass, conf)
        await rest.async_update(log_errors=False)

    if rest.data is None:
        if rest.last_exception:
            raise PlatformNotReady from rest.last_exception
        raise PlatformNotReady

    unique_id = conf.get(CONF_UNIQUE_ID)

    async_add_entities(
        [
            RestBinarySensor(
                hass,
                coordinator,
                rest,
                conf,
                unique_id,
            )
        ],
    )


class RestBinarySensor(RestEntity, TemplateEntity, BinarySensorEntity):
    """Representation of a REST binary sensor."""

    def __init__(
        self,
        hass,
        coordinator,
        rest,
        config,
        unique_id,
    ):
        """Initialize a REST binary sensor."""
        RestEntity.__init__(
            self,
            coordinator,
            rest,
            config.get(CONF_RESOURCE_TEMPLATE),
            config.get(CONF_FORCE_UPDATE),
        )
        TemplateEntity.__init__(
            self,
            hass,
            config=config,
            fallback_name=DEFAULT_BINARY_SENSOR_NAME,
            unique_id=unique_id,
        )
        self._state = False
        self._previous_data = None
        self._value_template = config.get(CONF_VALUE_TEMPLATE)
        if (value_template := self._value_template) is not None:
            value_template.hass = hass
        self._is_on = None

        self._attr_device_class = config.get(CONF_DEVICE_CLASS)

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._is_on

    def _update_from_rest_data(self):
        """Update state from the rest data."""
        if self.rest.data is None:
            self._is_on = False

        response = self.rest.data

        if self._value_template is not None:
            response = self._value_template.async_render_with_possible_json_value(
                self.rest.data, False
            )

        try:
            self._is_on = bool(int(response))
        except ValueError:
            self._is_on = {"true": True, "on": True, "open": True, "yes": True}.get(
                response.lower(), False
            )
