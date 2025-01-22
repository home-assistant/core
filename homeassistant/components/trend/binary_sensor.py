"""A sensor that monitors trends in other components."""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping
import logging
import math
from typing import Any

import numpy as np
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA,
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA as BINARY_SENSOR_PLATFORM_SCHEMA,
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    CONF_ATTRIBUTE,
    CONF_DEVICE_CLASS,
    CONF_ENTITY_ID,
    CONF_FRIENDLY_NAME,
    CONF_SENSORS,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device import async_device_info_to_link_from_entity
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.dt import utcnow

from . import PLATFORMS
from .const import (
    ATTR_GRADIENT,
    ATTR_INVERT,
    ATTR_MIN_GRADIENT,
    ATTR_SAMPLE_COUNT,
    ATTR_SAMPLE_DURATION,
    CONF_INVERT,
    CONF_MAX_SAMPLES,
    CONF_MIN_GRADIENT,
    CONF_MIN_SAMPLES,
    CONF_SAMPLE_DURATION,
    DEFAULT_MAX_SAMPLES,
    DEFAULT_MIN_GRADIENT,
    DEFAULT_MIN_SAMPLES,
    DEFAULT_SAMPLE_DURATION,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _validate_min_max(data: dict[str, Any]) -> dict[str, Any]:
    if (
        CONF_MIN_SAMPLES in data
        and CONF_MAX_SAMPLES in data
        and data[CONF_MAX_SAMPLES] < data[CONF_MIN_SAMPLES]
    ):
        raise vol.Invalid("min_samples must be smaller than or equal to max_samples")
    return data


SENSOR_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(CONF_ENTITY_ID): cv.entity_id,
            vol.Optional(CONF_ATTRIBUTE): cv.string,
            vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
            vol.Optional(CONF_FRIENDLY_NAME): cv.string,
            vol.Optional(CONF_INVERT, default=False): cv.boolean,
            vol.Optional(CONF_MAX_SAMPLES, default=2): cv.positive_int,
            vol.Optional(CONF_MIN_GRADIENT, default=0.0): vol.Coerce(float),
            vol.Optional(CONF_SAMPLE_DURATION, default=0): cv.positive_int,
            vol.Optional(CONF_MIN_SAMPLES, default=2): cv.positive_int,
        }
    ),
    _validate_min_max,
)

PLATFORM_SCHEMA = BINARY_SENSOR_PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_SENSORS): cv.schema_with_slug_keys(SENSOR_SCHEMA)}
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the trend sensors."""
    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)

    entities = []
    for sensor_name, sensor_config in config[CONF_SENSORS].items():
        entities.append(
            SensorTrend(
                name=sensor_config.get(CONF_FRIENDLY_NAME, sensor_name),
                entity_id=sensor_config[CONF_ENTITY_ID],
                attribute=sensor_config.get(CONF_ATTRIBUTE),
                invert=sensor_config[CONF_INVERT],
                sample_duration=sensor_config[CONF_SAMPLE_DURATION],
                min_gradient=sensor_config[CONF_MIN_GRADIENT],
                min_samples=sensor_config[CONF_MIN_SAMPLES],
                max_samples=sensor_config[CONF_MAX_SAMPLES],
                device_class=sensor_config.get(CONF_DEVICE_CLASS),
                sensor_entity_id=generate_entity_id(
                    ENTITY_ID_FORMAT, sensor_name, hass=hass
                ),
            )
        )

    async_add_entities(entities)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up trend sensor from config entry."""

    device_info = async_device_info_to_link_from_entity(
        hass,
        entry.options[CONF_ENTITY_ID],
    )

    async_add_entities(
        [
            SensorTrend(
                name=entry.title,
                entity_id=entry.options[CONF_ENTITY_ID],
                attribute=entry.options.get(CONF_ATTRIBUTE),
                invert=entry.options[CONF_INVERT],
                sample_duration=entry.options.get(
                    CONF_SAMPLE_DURATION, DEFAULT_SAMPLE_DURATION
                ),
                min_gradient=entry.options.get(CONF_MIN_GRADIENT, DEFAULT_MIN_GRADIENT),
                min_samples=entry.options.get(CONF_MIN_SAMPLES, DEFAULT_MIN_SAMPLES),
                max_samples=entry.options.get(CONF_MAX_SAMPLES, DEFAULT_MAX_SAMPLES),
                unique_id=entry.entry_id,
                device_info=device_info,
            )
        ]
    )


class SensorTrend(BinarySensorEntity, RestoreEntity):
    """Representation of a trend Sensor."""

    _attr_should_poll = False
    _gradient = 0.0
    _state: bool | None = None

    def __init__(
        self,
        name: str,
        entity_id: str,
        attribute: str | None,
        invert: bool,
        sample_duration: int,
        min_gradient: float,
        min_samples: int,
        max_samples: int,
        unique_id: str | None = None,
        device_class: BinarySensorDeviceClass | None = None,
        sensor_entity_id: str | None = None,
        device_info: dr.DeviceInfo | None = None,
    ) -> None:
        """Initialize the sensor."""
        self._entity_id = entity_id
        self._attribute = attribute
        self._invert = invert
        self._sample_duration = sample_duration
        self._min_gradient = min_gradient
        self._min_samples = min_samples
        self.samples: deque = deque(maxlen=int(max_samples))

        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_unique_id = unique_id
        self._attr_device_info = device_info

        if sensor_entity_id:
            self.entity_id = sensor_entity_id

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return the state attributes of the sensor."""
        return {
            ATTR_ENTITY_ID: self._entity_id,
            ATTR_FRIENDLY_NAME: self._attr_name,
            ATTR_GRADIENT: self._gradient,
            ATTR_INVERT: self._invert,
            ATTR_MIN_GRADIENT: self._min_gradient,
            ATTR_SAMPLE_COUNT: len(self.samples),
            ATTR_SAMPLE_DURATION: self._sample_duration,
        }

    async def async_added_to_hass(self) -> None:
        """Complete device setup after being added to hass."""

        @callback
        def trend_sensor_state_listener(
            event: Event[EventStateChangedData],
        ) -> None:
            """Handle state changes on the observed device."""
            if (new_state := event.data["new_state"]) is None:
                return
            try:
                if self._attribute:
                    state = new_state.attributes.get(self._attribute)
                else:
                    state = new_state.state

                if state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                    self._attr_available = False
                else:
                    self._attr_available = True
                    sample = (new_state.last_updated.timestamp(), float(state))  # type: ignore[arg-type]
                    self.samples.append(sample)

                self.async_schedule_update_ha_state(True)
            except (ValueError, TypeError) as ex:
                _LOGGER.error(ex)

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._entity_id], trend_sensor_state_listener
            )
        )

        if not (state := await self.async_get_last_state()):
            return
        if state.state in {STATE_UNKNOWN, STATE_UNAVAILABLE}:
            return
        self._attr_is_on = state.state == STATE_ON

    async def async_update(self) -> None:
        """Get the latest data and update the states."""
        # Remove outdated samples
        if self._sample_duration > 0:
            cutoff = utcnow().timestamp() - self._sample_duration
            while self.samples and self.samples[0][0] < cutoff:
                self.samples.popleft()

        if len(self.samples) < self._min_samples:
            return

        # Calculate gradient of linear trend
        await self.hass.async_add_executor_job(self._calculate_gradient)

        # Update state
        self._attr_is_on = (
            abs(self._gradient) > abs(self._min_gradient)
            and math.copysign(self._gradient, self._min_gradient) == self._gradient
        )

        if self._invert:
            self._attr_is_on = not self._attr_is_on

    def _calculate_gradient(self) -> None:
        """Compute the linear trend gradient of the current samples.

        This need run inside executor.
        """
        timestamps = np.array([t for t, _ in self.samples])
        values = np.array([s for _, s in self.samples])
        coeffs = np.polyfit(timestamps, values, 1)
        self._gradient = coeffs[0]
