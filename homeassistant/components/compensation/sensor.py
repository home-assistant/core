"""Support for compensation sensor."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    CONF_STATE_CLASS,
    SensorEntity,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_ATTRIBUTE,
    CONF_DEVICE_CLASS,
    CONF_MAXIMUM,
    CONF_MINIMUM,
    CONF_NAME,
    CONF_SOURCE,
    CONF_UNIQUE_ID,
    CONF_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CONF_COMPENSATION,
    CONF_POLYNOMIAL,
    CONF_PRECISION,
    DATA_COMPENSATION,
    DEFAULT_NAME,
)

_LOGGER = logging.getLogger(__name__)

ATTR_COEFFICIENTS = "coefficients"
ATTR_SOURCE = "source"
ATTR_SOURCE_ATTRIBUTE = "source_attribute"


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Compensation sensor."""
    if discovery_info is None:
        return

    compensation: str = discovery_info[CONF_COMPENSATION]
    conf: dict[str, Any] = hass.data[DATA_COMPENSATION][compensation]

    source: str = conf[CONF_SOURCE]
    attribute: str | None = conf.get(CONF_ATTRIBUTE)
    if not (name := conf.get(CONF_NAME)):
        name = f"{DEFAULT_NAME} {source}"
        if attribute is not None:
            name = f"{name} {attribute}"

    async_add_entities(
        [CompensationSensor(conf.get(CONF_UNIQUE_ID), name, source, attribute, conf)]
    )


class CompensationSensor(SensorEntity):
    """Representation of a Compensation sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        unique_id: str | None,
        name: str,
        source: str,
        attribute: str | None,
        config: dict[str, Any],
    ) -> None:
        """Initialize the Compensation sensor."""

        self._attr_name = name
        self._source_entity_id = source
        self._source_attribute = attribute

        self._precision = config[CONF_PRECISION]
        self._attr_native_unit_of_measurement = config.get(CONF_UNIT_OF_MEASUREMENT)

        polynomial: np.poly1d = config[CONF_POLYNOMIAL]
        self._poly = polynomial
        self._coefficients = polynomial.coefficients.tolist()

        self._attr_unique_id = unique_id
        self._minimum = config[CONF_MINIMUM]
        self._maximum = config[CONF_MAXIMUM]

        self._attr_device_class = config.get(CONF_DEVICE_CLASS)
        self._attr_state_class = config.get(CONF_STATE_CLASS)

    async def async_added_to_hass(self) -> None:
        """Handle added to Hass."""
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._source_entity_id],
                self._async_compensation_sensor_state_listener,
            )
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the sensor."""
        ret = {
            ATTR_SOURCE: self._source_entity_id,
            ATTR_COEFFICIENTS: self._coefficients,
        }
        if self._source_attribute:
            ret[ATTR_SOURCE_ATTRIBUTE] = self._source_attribute
        return ret

    @callback
    def _async_compensation_sensor_state_listener(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Handle sensor state changes."""
        new_state: State | None
        if (new_state := event.data["new_state"]) is None:
            _LOGGER.warning(
                "While updating compensation %s, the new_state is None", self.name
            )
            self._attr_native_value = None
            self.async_write_ha_state()
            return

        if new_state.state == STATE_UNKNOWN:
            self._attr_native_value = None
            self.async_write_ha_state()
            return

        if new_state.state == STATE_UNAVAILABLE:
            self._attr_available = False
            self.async_write_ha_state()
            return

        self._attr_available = True

        if self.native_unit_of_measurement is None and self._source_attribute is None:
            self._attr_native_unit_of_measurement = new_state.attributes.get(
                ATTR_UNIT_OF_MEASUREMENT
            )

        if self._attr_device_class is None and (
            device_class := new_state.attributes.get(ATTR_DEVICE_CLASS)
        ):
            self._attr_device_class = device_class

        if self._attr_state_class is None and (
            state_class := new_state.attributes.get(ATTR_STATE_CLASS)
        ):
            self._attr_state_class = state_class

        if self._source_attribute:
            value = new_state.attributes.get(self._source_attribute)
        else:
            value = None if new_state.state == STATE_UNKNOWN else new_state.state
        try:
            x_value = float(value)  # type: ignore[arg-type]
            if self._minimum is not None and x_value <= self._minimum[0]:
                y_value = self._minimum[1]
            elif self._maximum is not None and x_value >= self._maximum[0]:
                y_value = self._maximum[1]
            else:
                y_value = self._poly(x_value)
            self._attr_native_value = round(y_value, self._precision)

        except (ValueError, TypeError):
            self._attr_native_value = None
            if self._source_attribute:
                _LOGGER.warning(
                    "%s attribute %s is not numerical",
                    self._source_entity_id,
                    self._source_attribute,
                )
            else:
                _LOGGER.warning("%s state is not numerical", self._source_entity_id)

        self.async_write_ha_state()
