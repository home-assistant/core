"""Support for RESTful API sensors."""

from __future__ import annotations

import logging
import ssl
from typing import Any
from xml.parsers.expat import ExpatError

import voluptuous as vol

from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    DOMAIN as SENSOR_DOMAIN,
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
)
from homeassistant.components.sensor.helpers import async_parse_date_datetime
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_FORCE_UPDATE,
    CONF_ICON,
    CONF_NAME,
    CONF_RESOURCE,
    CONF_RESOURCE_TEMPLATE,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.template import Template
from homeassistant.helpers.trigger_template_entity import (
    CONF_AVAILABILITY,
    CONF_PICTURE,
    ManualTriggerSensorEntity,
    ValueTemplate,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import async_get_config_and_coordinator, create_rest_data_from_config
from .const import CONF_JSON_ATTRS, CONF_JSON_ATTRS_PATH, DEFAULT_SENSOR_NAME
from .data import RestData
from .entity import RestEntity
from .schema import RESOURCE_SCHEMA, SENSOR_SCHEMA
from .util import parse_json_attributes

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = vol.All(
    SENSOR_PLATFORM_SCHEMA.extend({**RESOURCE_SCHEMA, **SENSOR_SCHEMA}),
    cv.has_at_least_one_key(CONF_RESOURCE, CONF_RESOURCE_TEMPLATE),
)

TRIGGER_ENTITY_OPTIONS = (
    CONF_AVAILABILITY,
    CONF_DEVICE_CLASS,
    CONF_ICON,
    CONF_PICTURE,
    CONF_UNIQUE_ID,
    CONF_STATE_CLASS,
    CONF_UNIT_OF_MEASUREMENT,
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the RESTful sensor."""
    # Must update the sensor now (including fetching the rest resource) to
    # ensure it's updating its state.
    if discovery_info is not None:
        conf, coordinator, rest = await async_get_config_and_coordinator(
            hass, SENSOR_DOMAIN, discovery_info
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

    name = conf.get(CONF_NAME) or Template(DEFAULT_SENSOR_NAME, hass)

    trigger_entity_config = {CONF_NAME: name}

    for key in TRIGGER_ENTITY_OPTIONS:
        if key not in conf:
            continue
        trigger_entity_config[key] = conf[key]

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
    def available(self) -> bool:
        """Return if entity is available."""
        available1 = RestEntity.available.fget(self)  # type: ignore[attr-defined]
        available2 = ManualTriggerSensorEntity.available.fget(self)  # type: ignore[attr-defined]
        return bool(available1 and available2)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        return dict(self._attr_extra_state_attributes)

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

        if value is None or self.device_class not in (
            SensorDeviceClass.DATE,
            SensorDeviceClass.TIMESTAMP,
        ):
            self._attr_native_value = value
            self._process_manual_data(variables)
            self.async_write_ha_state()
            return

        self._attr_native_value = async_parse_date_datetime(
            value, self.entity_id, self.device_class
        )

        self._process_manual_data(variables)
        self.async_write_ha_state()
