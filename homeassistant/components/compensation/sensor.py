"""Support for compensation sensor."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_ATTRIBUTE,
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_SOURCE,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, EventType

from .const import (
    ATTR_COEFFICIENTS,
    ATTR_SOURCE,
    ATTR_SOURCE_ATTRIBUTE,
    ATTR_SOURCE_VALUE,
    CONF_COMPENSATION,
    CONF_POLYNOMIAL,
    CONF_PRECISION,
    DATA_COMPENSATION,
    DEFAULT_NAME,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Compensation sensor."""
    if discovery_info is None:
        return

    compensation = discovery_info[CONF_COMPENSATION]
    conf = hass.data[DATA_COMPENSATION][compensation]

    source = conf[CONF_SOURCE]
    attribute = conf.get(CONF_ATTRIBUTE)
    name = f"{DEFAULT_NAME} {source}"
    if attribute:
        name = f"{name} {attribute}"
    name = conf.get(CONF_NAME) or name

    async_add_entities(
        [
            CompensationSensor(
                conf.get(CONF_UNIQUE_ID),
                name,
                source,
                attribute,
                conf[CONF_PRECISION],
                conf[CONF_POLYNOMIAL],
                conf.get(CONF_UNIT_OF_MEASUREMENT),
                conf.get(CONF_DEVICE_CLASS),
            )
        ]
    )


class CompensationSensor(SensorEntity):
    """Representation of a Compensation sensor."""

    def __init__(
        self,
        unique_id: str,
        name: str,
        source: str,
        attribute: str | None,
        precision: int,
        polynomial,
        unit_of_measurement: str,
        device_class: str,
    ) -> None:
        """Initialize the Compensation sensor."""
        self._source_entity_id = source
        self._precision = precision
        self._source_attribute = attribute
        self._attr_native_unit_of_measurement = unit_of_measurement
        self._poly = polynomial
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._attr_should_poll = False
        self._attr_device_class = device_class

        attrs = {
            ATTR_SOURCE_VALUE: None,
            ATTR_SOURCE: source,
            ATTR_SOURCE_ATTRIBUTE: attribute,
            ATTR_COEFFICIENTS: polynomial.coef.tolist(),
        }
        self._attr_extra_state_attributes = {
            k: v for k, v in attrs.items() if v or k != ATTR_SOURCE_ATTRIBUTE
        }

    async def async_added_to_hass(self) -> None:
        """Handle added to Hass."""
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._source_entity_id],
                self._async_compensation_sensor_state_listener,
            )
        )

    @callback
    def _async_compensation_sensor_state_listener(self, event: EventType) -> None:
        """Handle sensor state changes."""
        if (new_state := event.data.get("new_state")) is None:
            return

        if self._source_attribute is None:
            if self._attr_native_unit_of_measurement is None:
                self._attr_native_unit_of_measurement = new_state.attributes.get(
                    ATTR_UNIT_OF_MEASUREMENT
                )
            if self._attr_device_class is None:
                self._attr_device_class = new_state.attributes.get(ATTR_DEVICE_CLASS)

        try:
            source_value = (
                float(new_state.attributes.get(self._source_attribute))
                if self._source_attribute
                else float(new_state.state)
                if new_state.state != STATE_UNKNOWN
                else None
            )
            native_value = round(self._poly(source_value), self._precision)
        except (ValueError, TypeError):
            source_value = native_value = None
            if self._source_attribute:
                _LOGGER.warning(
                    "%s attribute %s is not numerical",
                    self._source_entity_id,
                    self._source_attribute,
                )
            else:
                _LOGGER.warning("%s state is not numerical", self._source_entity_id)

        self._attr_extra_state_attributes[ATTR_SOURCE_VALUE] = source_value
        self._attr_native_value = native_value

        self.async_write_ha_state()
