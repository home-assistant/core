"""Support for RESTful API sensors."""
from __future__ import annotations

import logging
import ssl
from typing import Any

from jsonpath import jsonpath
import voluptuous as vol

from homeassistant.components.sensor import (
    CONF_STATE_CLASS,
    DOMAIN as SENSOR_DOMAIN,
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
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
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.template import Template
from homeassistant.helpers.template_entity import (
    CONF_AVAILABILITY,
    CONF_PICTURE,
    ManualTriggerEntity,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.json import json_loads

from . import async_get_config_and_coordinator, create_rest_data_from_config
from .const import CONF_JSON_ATTRS, CONF_JSON_ATTRS_PATH, DEFAULT_SENSOR_NAME
from .data import RestData
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
            if isinstance(rest.last_exception, ssl.SSLError):
                _LOGGER.error(
                    "Error connecting %s failed with %s",
                    rest.url,
                    rest.last_exception,
                )
                return
            raise PlatformNotReady from rest.last_exception
        raise PlatformNotReady

    unit_of_measurement = conf.get(CONF_UNIT_OF_MEASUREMENT)
    state_class = conf.get(CONF_STATE_CLASS)

    name = conf.get(CONF_NAME)
    if not name:
        name = Template(DEFAULT_SENSOR_NAME, hass)

    trigger_entity_config = {
        CONF_NAME: name,
        CONF_DEVICE_CLASS: conf.get(CONF_DEVICE_CLASS),
        CONF_UNIQUE_ID: conf.get(CONF_UNIQUE_ID),
    }
    if available := conf.get(CONF_AVAILABILITY):
        trigger_entity_config[CONF_AVAILABILITY] = available
    if icon := conf.get(CONF_ICON):
        trigger_entity_config[CONF_ICON] = icon
    if picture := conf.get(CONF_PICTURE):
        trigger_entity_config[CONF_PICTURE] = picture

    async_add_entities(
        [
            RestSensor(
                hass,
                coordinator,
                rest,
                conf,
                trigger_entity_config,
                unit_of_measurement,
                state_class,
            )
        ],
    )


class RestSensor(ManualTriggerEntity, RestEntity, SensorEntity):
    """Implementation of a REST sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: DataUpdateCoordinator[None] | None,
        rest: RestData,
        config: ConfigType,
        trigger_entity_config: ConfigType,
        unit_of_measurement: str | None,
        state_class: str | None,
    ) -> None:
        """Initialize the REST sensor."""
        ManualTriggerEntity.__init__(self, hass, trigger_entity_config)
        RestEntity.__init__(
            self,
            coordinator,
            rest,
            config.get(CONF_RESOURCE_TEMPLATE),
            config[CONF_FORCE_UPDATE],
        )
        self._attr_native_unit_of_measurement = unit_of_measurement
        self._attr_state_class = state_class
        self._value_template = config.get(CONF_VALUE_TEMPLATE)
        if (value_template := self._value_template) is not None:
            value_template.hass = hass
        self._json_attrs = config.get(CONF_JSON_ATTRS)
        self._json_attrs_path = config.get(CONF_JSON_ATTRS_PATH)
        self._attr_extra_state_attributes = {}

    async def async_added_to_hass(self) -> None:
        """Ensure the data from the initial update is reflected in the state."""
        await RestEntity.async_added_to_hass(self)
        await ManualTriggerEntity.async_added_to_hass(self)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        available1 = RestEntity.available.fget(self)  # type: ignore[attr-defined]
        available2 = ManualTriggerEntity.available.fget(self)  # type: ignore[attr-defined]
        return bool(available1 and available2)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        return dict(self._attr_extra_state_attributes)

    def _update_from_rest_data(self) -> None:
        """Update state from the rest data."""
        value = self.rest.data_without_xml()

        if self._json_attrs:
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
                        self._attr_extra_state_attributes = attrs
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

        raw_value = value

        if value is not None and self._value_template is not None:
            value = self._value_template.async_render_with_possible_json_value(
                value, None
            )

        if value is None or self.device_class not in (
            SensorDeviceClass.DATE,
            SensorDeviceClass.TIMESTAMP,
        ):
            self._attr_native_value = value
            self._process_manual_data(raw_value)
            self.async_write_ha_state()
            return

        self._attr_native_value = async_parse_date_datetime(
            value, self.entity_id, self.device_class
        )

        self._process_manual_data(raw_value)
        self.async_write_ha_state()
