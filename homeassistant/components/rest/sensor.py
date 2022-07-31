"""Support for RESTful API sensors."""
from __future__ import annotations

import logging
from xml.parsers.expat import ExpatError

from jsonpath import jsonpath
import voluptuous as vol
import xmltodict

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    PLATFORM_SCHEMA,
    SensorDeviceClass,
)
from homeassistant.components.sensor.helpers import async_parse_date_datetime
from homeassistant.const import (
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
from homeassistant.helpers.json import json_dumps, json_loads
from homeassistant.helpers.template_entity import TemplateSensor
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import async_get_config_and_coordinator, create_rest_data_from_config
from .const import CONF_JSON_ATTRS, CONF_JSON_ATTRS_PATH, DEFAULT_SENSOR_NAME
from .entity import RestEntity
from .schema import RESOURCE_SCHEMA, SENSOR_SCHEMA

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({**RESOURCE_SCHEMA, **SENSOR_SCHEMA})

PLATFORM_SCHEMA = vol.All(
    cv.has_at_least_one_key(CONF_RESOURCE, CONF_RESOURCE_TEMPLATE), PLATFORM_SCHEMA
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
            raise PlatformNotReady from rest.last_exception
        raise PlatformNotReady

    unique_id = conf.get(CONF_UNIQUE_ID)

    async_add_entities(
        [
            RestSensor(
                hass,
                coordinator,
                rest,
                conf,
                unique_id,
            )
        ],
    )


class RestSensor(RestEntity, TemplateSensor):
    """Implementation of a REST sensor."""

    def __init__(
        self,
        hass,
        coordinator,
        rest,
        config,
        unique_id,
    ):
        """Initialize the REST sensor."""
        RestEntity.__init__(
            self,
            coordinator,
            rest,
            config.get(CONF_RESOURCE_TEMPLATE),
            config.get(CONF_FORCE_UPDATE),
        )
        TemplateSensor.__init__(
            self,
            hass,
            config=config,
            fallback_name=DEFAULT_SENSOR_NAME,
            unique_id=unique_id,
        )
        self._state = None
        self._value_template = config.get(CONF_VALUE_TEMPLATE)
        if (value_template := self._value_template) is not None:
            value_template.hass = hass
        self._json_attrs = config.get(CONF_JSON_ATTRS)
        self._attributes = None
        self._json_attrs_path = config.get(CONF_JSON_ATTRS_PATH)

    @property
    def native_value(self):
        """Return the state of the device."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    def _update_from_rest_data(self):
        """Update state from the rest data."""
        value = self.rest.data
        _LOGGER.debug("Data fetched from resource: %s", value)
        if self.rest.headers is not None:
            # If the http request failed, headers will be None
            content_type = self.rest.headers.get("content-type")

            if content_type and (
                content_type.startswith("text/xml")
                or content_type.startswith("application/xml")
                or content_type.startswith("application/xhtml+xml")
                or content_type.startswith("application/rss+xml")
            ):
                try:
                    value = json_dumps(xmltodict.parse(value))
                    _LOGGER.debug("JSON converted from XML: %s", value)
                except ExpatError:
                    _LOGGER.warning(
                        "REST xml result could not be parsed and converted to JSON"
                    )
                    _LOGGER.debug("Erroneous XML: %s", value)

        if self._json_attrs:
            self._attributes = {}
            if value:
                try:
                    json_dict = json_loads(value)
                    if self._json_attrs_path is not None:
                        json_dict = jsonpath(json_dict, self._json_attrs_path)
                    # jsonpath will always store the result in json_dict[0]
                    # so the next line happens to work exactly as needed to
                    # find the result
                    if isinstance(json_dict, list):
                        json_dict = json_dict[0]
                    if isinstance(json_dict, dict):
                        attrs = {
                            k: json_dict[k] for k in self._json_attrs if k in json_dict
                        }
                        self._attributes = attrs
                    else:
                        _LOGGER.warning(
                            "JSON result was not a dictionary"
                            " or list with 0th element a dictionary"
                        )
                except ValueError:
                    _LOGGER.warning("REST result could not be parsed as JSON")
                    _LOGGER.debug("Erroneous JSON: %s", value)

            else:
                _LOGGER.warning("Empty reply found when expecting JSON data")

        if value is not None and self._value_template is not None:
            value = self._value_template.async_render_with_possible_json_value(
                value, None
            )

        if value is None or self.device_class not in (
            SensorDeviceClass.DATE,
            SensorDeviceClass.TIMESTAMP,
        ):
            self._state = value
            return

        self._state = async_parse_date_datetime(
            value, self.entity_id, self.device_class
        )
