"""A sensor that monitors trends in other components."""
from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import math
from typing import Any, cast

import numpy as np
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA,
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ATTRIBUTE,
    CONF_DEVICE_CLASS,
    CONF_ENTITY_ID,
    CONF_FRIENDLY_NAME,
    CONF_SENSORS,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant, State, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    async_track_state_change_event,
)
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

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
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _check_sample_options(config: ConfigType) -> ConfigType:
    """Check min/max sample options."""
    if config[CONF_MAX_SAMPLES] < config[CONF_MIN_SAMPLES]:
        raise vol.Invalid(
            f"{CONF_MAX_SAMPLES} must not be smaller than {CONF_MIN_SAMPLES}"
        )
    return config


SENSOR_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(CONF_ENTITY_ID): cv.entity_id,
            vol.Optional(CONF_ATTRIBUTE): cv.string,
            vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
            vol.Optional(CONF_FRIENDLY_NAME): cv.string,
            vol.Optional(CONF_INVERT, default=False): cv.boolean,
            vol.Optional(CONF_MAX_SAMPLES, default=2): vol.All(
                vol.Coerce(int), vol.Range(min=2)
            ),
            vol.Optional(CONF_MIN_GRADIENT, default=0.0): vol.Coerce(float),
            vol.Optional(CONF_MIN_SAMPLES, default=2): vol.All(
                vol.Coerce(int), vol.Range(min=2)
            ),
            vol.Optional(CONF_SAMPLE_DURATION, default=0): cv.positive_time_period,
        }
    ),
    _check_sample_options,
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_SENSORS): cv.schema_with_slug_keys(SENSOR_SCHEMA)}
)


@dataclass
class Sample:
    """Trend sample."""

    time: datetime
    value: float


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the trend sensors."""
    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)

    async_add_entities(
        [
            SensorTrend(
                BinarySensorEntityDescription(
                    key=async_generate_entity_id(
                        ENTITY_ID_FORMAT, device_id, hass=hass
                    ),
                    device_class=device_config.get(CONF_DEVICE_CLASS),
                    name=device_config.get(CONF_FRIENDLY_NAME, device_id),
                ),
                device_config,
            )
            for device_id, device_config in cast(
                ConfigType, config[CONF_SENSORS]
            ).items()
        ]
    )


class SensorTrend(BinarySensorEntity):
    """Representation of a trend Sensor."""

    _attr_should_poll = False
    _unsub: Callable[..., None] | None = None

    def __init__(
        self,
        entity_description: BinarySensorEntityDescription,
        config: ConfigType,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = entity_description
        self.entity_id = entity_description.key

        self._entity_id: str = config[ATTR_ENTITY_ID]
        self._attribute: str | None = config.get(CONF_ATTRIBUTE)
        self._invert: bool = config[CONF_INVERT]
        self._sample_duration: timedelta = config[CONF_SAMPLE_DURATION]
        self._min_gradient: float = config[CONF_MIN_GRADIENT]
        self._min_samples: int = config[CONF_MIN_SAMPLES]

        self._attr_extra_state_attributes = {
            ATTR_ENTITY_ID: self._entity_id,
            ATTR_GRADIENT: None,
            ATTR_INVERT: self._invert,
            ATTR_MIN_GRADIENT: self._min_gradient,
            ATTR_SAMPLE_COUNT: 0,
            ATTR_SAMPLE_DURATION: self._sample_duration.total_seconds(),
        }

        self._samples: deque[Sample] = deque(maxlen=config[CONF_MAX_SAMPLES])

        def unsub():
            if self._unsub:
                self._unsub()
                self._unsub = None

        self.async_on_remove(unsub)

    @property
    def _gradient(self) -> float | None:
        """Return gradient."""
        return self._attr_extra_state_attributes[ATTR_GRADIENT]

    @_gradient.setter
    def _gradient(self, gradient: float | None) -> None:
        """Set gradient."""
        self._attr_extra_state_attributes[ATTR_GRADIENT] = gradient

    def _remove_oldest_sample(self) -> None:
        """Remove oldest sample."""
        self._samples.popleft()
        self._attr_extra_state_attributes[ATTR_SAMPLE_COUNT] = len(self._samples)

    def _add_sample(self, sample: Sample) -> None:
        """Add new sample."""
        self._samples.append(sample)
        self._attr_extra_state_attributes[ATTR_SAMPLE_COUNT] = len(self._samples)

    async def async_added_to_hass(self) -> None:
        """Complete device setup after being added to hass."""

        @callback
        def remove_stale_sample(remove_time: datetime) -> None:
            """Remove stale sample."""
            self._remove_oldest_sample()
            if self._samples:
                self._unsub = async_track_point_in_utc_time(
                    self.hass,
                    remove_stale_sample,
                    self._samples[0].time + self._sample_duration,
                )
            else:
                self._unsub = None
            self.async_schedule_update_ha_state(True)

        @callback
        def trend_sensor_state_listener(event: Event) -> None:
            """Handle state changes on the observed device."""
            if (new_state := cast(State | Any, event.data.get("new_state"))) is None:
                return
            if self._attribute:
                state = new_state.attributes.get(self._attribute)
            else:
                state = new_state.state
            if state in (None, STATE_UNKNOWN, STATE_UNAVAILABLE):
                return

            samle_count_was = len(self._samples)

            try:
                sample = Sample(new_state.last_updated, float(state))  # type: ignore[arg-type]
            except (TypeError, ValueError):
                _LOGGER.error("Input value %s for %s is not a number", state, self.name)
                return

            self._add_sample(sample)

            if self._sample_duration and samle_count_was in [
                0,
                self._samples.maxlen,
            ]:
                if self._unsub:
                    self._unsub()
                self._unsub = async_track_point_in_utc_time(
                    self.hass,
                    remove_stale_sample,
                    self._samples[0].time + self._sample_duration,
                )

            self.async_schedule_update_ha_state(True)

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._entity_id], trend_sensor_state_listener
            )
        )

    async def async_update(self) -> None:
        """Get the latest data and update the states."""
        if len(self._samples) < self._min_samples:
            self._gradient = None
            self._attr_is_on = None
            return

        def calculate_gradient() -> float:
            """Compute the linear trend gradient of the current samples.

            This need run inside executor.
            """
            timestamps = np.array([s.time.timestamp() for s in self._samples])
            values = np.array([s.value for s in self._samples])
            coeffs = np.polyfit(timestamps, values, 1)
            return coeffs[0]

        # Calculate gradient of linear trend
        self._gradient = await self.hass.async_add_executor_job(calculate_gradient)

        # Update state
        self._attr_is_on = (
            abs(self._gradient) > abs(self._min_gradient)
            and math.copysign(self._gradient, self._min_gradient) == self._gradient
        )

        if self._invert:
            self._attr_is_on = not self._attr_is_on
