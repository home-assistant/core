"""Support for RESTful binary sensors."""

from __future__ import annotations

import logging
import ssl
from xml.parsers.expat import ExpatError

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DOMAIN as BINARY_SENSOR_DOMAIN,
    PLATFORM_SCHEMA as BINARY_SENSOR_PLATFORM_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_FORCE_UPDATE,
    CONF_ICON,
    CONF_NAME,
    CONF_RESOURCE,
    CONF_RESOURCE_TEMPLATE,
    CONF_UNIQUE_ID,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.template import Template
from homeassistant.helpers.trigger_template_entity import (
    CONF_AVAILABILITY,
    CONF_PICTURE,
    ManualTriggerEntity,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import async_get_config_and_coordinator, create_rest_data_from_config
from .const import DEFAULT_BINARY_SENSOR_NAME
from .data import RestData
from .entity import RestEntity
from .schema import BINARY_SENSOR_SCHEMA, RESOURCE_SCHEMA

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = vol.All(
    BINARY_SENSOR_PLATFORM_SCHEMA.extend({**RESOURCE_SCHEMA, **BINARY_SENSOR_SCHEMA}),
    cv.has_at_least_one_key(CONF_RESOURCE, CONF_RESOURCE_TEMPLATE),
)

TRIGGER_ENTITY_OPTIONS = (
    CONF_AVAILABILITY,
    CONF_DEVICE_CLASS,
    CONF_ICON,
    CONF_PICTURE,
    CONF_UNIQUE_ID,
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
            if isinstance(rest.last_exception, ssl.SSLError):
                _LOGGER.error(
                    "Error connecting %s failed with %s",
                    rest.url,
                    rest.last_exception,
                )
                return
            raise PlatformNotReady from rest.last_exception
        raise PlatformNotReady

    name = conf.get(CONF_NAME) or Template(DEFAULT_BINARY_SENSOR_NAME, hass)

    trigger_entity_config = {CONF_NAME: name}

    for key in TRIGGER_ENTITY_OPTIONS:
        if key not in conf:
            continue
        trigger_entity_config[key] = conf[key]

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
        self._value_template: Template | None = config.get(CONF_VALUE_TEMPLATE)
        if (value_template := self._value_template) is not None:
            value_template.hass = hass

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        available1 = RestEntity.available.fget(self)  # type: ignore[attr-defined]
        available2 = ManualTriggerEntity.available.fget(self)  # type: ignore[attr-defined]
        return bool(available1 and available2)

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

        raw_value = response

        if response is not None and self._value_template is not None:
            response = self._value_template.async_render_with_possible_json_value(
                response, False
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

        self._process_manual_data(raw_value)
        self.async_write_ha_state()
