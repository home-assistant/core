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
    PLATFORM_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    CONF_ATTRIBUTE,
    CONF_DEVICE_CLASS,
    CONF_ENTITY_ID,
    CONF_FRIENDLY_NAME,
    CONF_NAME,
    CONF_SENSORS,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    EventStateChangedData,
    async_track_state_change_event,
)
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, EventType
from homeassistant.util.dt import utcnow

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

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_SENSORS): cv.schema_with_slug_keys(SENSOR_SCHEMA)}
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the trend sensors."""

    for sensor_name, sensor_config in config[CONF_SENSORS].items():
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data={CONF_NAME: sensor_name, **sensor_config},
            )
        )

    async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version="2024.7.0",
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": "Trend",
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up trend sensor from config entry."""

    async_add_entities([SensorTrend(entry)])


class SensorTrend(BinarySensorEntity, RestoreEntity):
    """Representation of a trend Sensor."""

    _attr_should_poll = False
    _gradient = 0.0
    _state: bool | None = None

    def __init__(
        self,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        self._entity_id = config_entry.options[CONF_ENTITY_ID]
        self._attribute = config_entry.options.get(CONF_ATTRIBUTE)
        self._invert = config_entry.options[CONF_INVERT]
        self._sample_duration = config_entry.options.get(
            CONF_SAMPLE_DURATION, DEFAULT_SAMPLE_DURATION
        )
        self._min_gradient = config_entry.options.get(
            CONF_MIN_GRADIENT, DEFAULT_MIN_GRADIENT
        )
        self._min_samples = config_entry.options.get(
            CONF_MIN_SAMPLES, DEFAULT_MIN_SAMPLES
        )
        self.samples: deque = deque(
            maxlen=int(config_entry.options.get(CONF_MAX_SAMPLES, DEFAULT_MAX_SAMPLES))
        )

        # this is only available if imported from YAML
        # keep this for backwards compatibility
        self._attr_device_class = config_entry.options.get(CONF_DEVICE_CLASS)

        self._attr_unique_id = config_entry.entry_id
        self._attr_name = config_entry.title

    @property
    def is_on(self) -> bool | None:
        """Return true if sensor is on."""
        return self._state

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
            event: EventType[EventStateChangedData],
        ) -> None:
            """Handle state changes on the observed device."""
            if (new_state := event.data["new_state"]) is None:
                return
            try:
                if self._attribute:
                    state = new_state.attributes.get(self._attribute)
                else:
                    state = new_state.state
                if state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
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
        if state.state == STATE_UNKNOWN:
            return
        self._state = state.state == STATE_ON

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
        self._state = (
            abs(self._gradient) > abs(self._min_gradient)
            and math.copysign(self._gradient, self._min_gradient) == self._gradient
        )

        if self._invert:
            self._state = not self._state

    def _calculate_gradient(self) -> None:
        """Compute the linear trend gradient of the current samples.

        This need run inside executor.
        """
        timestamps = np.array([t for t, _ in self.samples])
        values = np.array([s for _, s in self.samples])
        coeffs = np.polyfit(timestamps, values, 1)
        self._gradient = coeffs[0]
