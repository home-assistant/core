"""A sensor that detects anomalies in other components."""
from collections import deque
import logging

import numpy as np
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASSES_SCHEMA,
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA,
    BinarySensorEntity,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    CONF_DEVICE_CLASS,
    CONF_ENTITY_ID,
    CONF_FRIENDLY_NAME,
    CONF_SENSORS,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import State, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.reload import setup_reload_service
from homeassistant.util import utcnow

from . import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

ATTR_ATTRIBUTE = "attribute"
ATTR_INVERT = "invert"
ATTR_REQUIRE_BOTH = "require_both"
ATTR_POSITIVE_ONLY = "positive_only"
ATTR_NEGATIVE_ONLY = "negative_only"
ATTR_MIN_CHANGE_AMOUNT = "min_change_amount"
ATTR_MIN_CHANGE_PERCENT = "min_change_percent"
ATTR_SAMPLE_DURATION = "sample_duration"
ATTR_MAX_SAMPLES = "max_samples"
ATTR_TRAILING_SAMPLE_DURATION = "trailing_sample_duration"
ATTR_MAX_TRAILING_SAMPLES = "max_trailing_samples"
ATTR_SAMPLE_COUNT = "sample_count"
ATTR_TRAILING_SAMPLE_COUNT = "trailing_sample_count"
ATTR_SAMPLE_AVG = "sample_average"
ATTR_TRAILING_AVG = "trailing_sample_average"
ATTR_CHANGE_AMOUNT = "change_amount"
ATTR_CHANGE_PERCENT = "change_percent"

CONF_ATTRIBUTE = "attribute"
CONF_INVERT = "invert"
CONF_POSITIVE_ONLY = "positive_only"
CONF_NEGATIVE_ONLY = "negative_only"
CONF_REQUIRE_BOTH = "require_both"
CONF_MAX_SAMPLES = "max_samples"
CONF_SAMPLE_DURATION = "sample_duration"
CONF_MAX_TRAILING_SAMPLES = "max_trailing_samples"
CONF_TRAILING_SAMPLE_DURATION = "trailing_sample_duration"
CONF_MIN_CHANGE_AMOUNT = "min_change_amount"
CONF_MIN_CHANGE_PERCENT = "min_change_percent"

SENSOR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Optional(CONF_ATTRIBUTE): cv.string,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
        vol.Optional(CONF_FRIENDLY_NAME): cv.string,
        vol.Optional(CONF_INVERT, default=False): cv.boolean,
        vol.Optional(CONF_REQUIRE_BOTH, default=False): cv.boolean,
        vol.Optional(CONF_POSITIVE_ONLY, default=False): cv.boolean,
        vol.Optional(CONF_NEGATIVE_ONLY, default=False): cv.boolean,
        vol.Optional(CONF_MAX_SAMPLES, default=1): cv.positive_int,
        vol.Optional(CONF_SAMPLE_DURATION, default=0): cv.positive_int,
        vol.Optional(CONF_MAX_TRAILING_SAMPLES, default=2): cv.positive_int,
        vol.Optional(CONF_TRAILING_SAMPLE_DURATION, default=0): cv.positive_int,
        vol.Optional(CONF_MIN_CHANGE_AMOUNT, default=0.0): vol.Coerce(float),
        vol.Optional(CONF_MIN_CHANGE_PERCENT, default=0.0): vol.Coerce(float),
    }
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_SENSORS): cv.schema_with_slug_keys(SENSOR_SCHEMA)}
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the anomaly sensors."""
    setup_reload_service(hass, DOMAIN, PLATFORMS)

    sensors = []

    for device_id, device_config in config[CONF_SENSORS].items():
        entity_id = device_config[ATTR_ENTITY_ID]
        attribute = device_config.get(CONF_ATTRIBUTE)
        device_class = device_config.get(CONF_DEVICE_CLASS)
        friendly_name = device_config.get(ATTR_FRIENDLY_NAME, device_id)
        invert = device_config[CONF_INVERT]
        require_both = device_config[CONF_REQUIRE_BOTH]
        positive_only = device_config[CONF_POSITIVE_ONLY]
        negative_only = device_config[CONF_NEGATIVE_ONLY]
        max_samples = device_config[CONF_MAX_SAMPLES]
        sample_duration = device_config[CONF_SAMPLE_DURATION]
        max_trailing_samples = device_config[CONF_MAX_TRAILING_SAMPLES]
        trailing_sample_duration = device_config[CONF_TRAILING_SAMPLE_DURATION]
        min_change_amount = device_config[CONF_MIN_CHANGE_AMOUNT]
        min_change_percent = device_config[CONF_MIN_CHANGE_PERCENT]

        sensors.append(
            SensorAnomaly(
                hass=hass,
                device_id=device_id,
                friendly_name=friendly_name,
                entity_id=entity_id,
                attribute=attribute,
                device_class=device_class,
                invert=invert,
                require_both=require_both,
                positive_only=positive_only,
                negative_only=negative_only,
                max_samples=max_samples,
                sample_duration=sample_duration,
                max_trailing_samples=max_trailing_samples,
                trailing_sample_duration=trailing_sample_duration,
                min_change_amount=min_change_amount,
                min_change_percent=min_change_percent,
            )
        )
    if not sensors:
        _LOGGER.error("No sensors added")
        return
    add_entities(sensors)
    return


class SensorAnomaly(BinarySensorEntity):
    """Representation of an anomaly Sensor."""

    def __init__(
        self,
        hass,
        device_id: str,
        friendly_name: str,
        entity_id: str,
        attribute: str,
        device_class: str,
        invert: bool,
        require_both: bool,
        positive_only: bool,
        negative_only: bool,
        max_samples: int,
        sample_duration: int,
        max_trailing_samples: int,
        trailing_sample_duration: int,
        min_change_amount: float,
        min_change_percent: float,
    ):
        """Initialize the sensor."""
        self._hass = hass
        self.entity_id: str = generate_entity_id(ENTITY_ID_FORMAT, device_id, hass=hass)
        self._name: str = friendly_name
        self._entity_id: str = entity_id
        self._attribute: str = attribute
        self._device_class: str = device_class
        self._invert: bool = invert
        self._require_both: bool = require_both
        self._positive_only: bool = positive_only
        self._negative_only: bool = negative_only
        self._max_samples: int = max_samples
        self._sample_duration: int = sample_duration
        self._max_trailing_samples: int = max_trailing_samples
        self._trailing_sample_duration: int = trailing_sample_duration
        self._min_change_amount: float = min_change_amount
        self._min_change_pct: float = min_change_percent
        self._change_amount: float = 0.0
        self._change_percent: float = 0.0
        self._trailing_avg: float = 0.0
        self._sample_avg: float = 0.0
        self._state = None
        self.trailing_samples: deque = deque(maxlen=max_trailing_samples)
        self.samples: deque = deque(maxlen=max_samples)

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self) -> str:
        """Return true if sensor is on."""
        return self._state

    @property
    def device_class(self) -> str:
        """Return the sensor class of the sensor."""
        return self._device_class

    @property
    def device_state_attributes(self) -> dict:
        """Return the state attributes of the sensor."""
        return {
            ATTR_ENTITY_ID: self._entity_id,
            ATTR_FRIENDLY_NAME: self._name,
            ATTR_INVERT: self._invert,
            ATTR_REQUIRE_BOTH: self._require_both,
            ATTR_POSITIVE_ONLY: self._positive_only,
            ATTR_NEGATIVE_ONLY: self._negative_only,
            ATTR_MIN_CHANGE_AMOUNT: self._min_change_amount,
            ATTR_MIN_CHANGE_PERCENT: self._min_change_pct,
            ATTR_SAMPLE_DURATION: self._sample_duration,
            ATTR_MAX_SAMPLES: self._max_samples,
            ATTR_TRAILING_SAMPLE_DURATION: self._trailing_sample_duration,
            ATTR_MAX_TRAILING_SAMPLES: self._max_trailing_samples,
            ATTR_SAMPLE_COUNT: len(self.samples),
            ATTR_TRAILING_SAMPLE_COUNT: len(self.trailing_samples),
            ATTR_SAMPLE_AVG: self._sample_avg,
            ATTR_TRAILING_AVG: self._trailing_avg,
            ATTR_CHANGE_AMOUNT: self._change_amount,
            ATTR_CHANGE_PERCENT: self._change_percent,
        }

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    async def async_added_to_hass(self) -> None:
        """Complete device setup after being added to hass."""

        @callback
        def anomaly_sensor_state_listener(event) -> None:
            """Handle state changes on the observed device."""
            new_state: State = event.data.get("new_state")
            if new_state is None:
                return
            try:
                if self._attribute:
                    state: str = new_state.attributes.get(self._attribute)
                else:
                    state: str = new_state.state
                if state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                    sample: tuple = (new_state.last_updated.timestamp(), float(state))
                    self.samples.append(sample)
                    self.trailing_samples.append(sample)
                    self.async_schedule_update_ha_state(True)
            except (ValueError, TypeError) as ex:
                _LOGGER.error(ex)
            return

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._entity_id], anomaly_sensor_state_listener
            )
        )
        return

    async def async_update(self) -> None:
        """Get the latest data and update the states."""
        # Remove outdated samples
        if self._trailing_sample_duration > 0:
            await self.hass.async_add_executor_job(self._trim_trailing_samples)
        if self._sample_duration > 0:
            await self.hass.async_add_executor_job(self._trim_samples)
        if len(self.samples) == 0:
            return

        # Calculate diffs between trailing and sample averages
        await self.hass.async_add_executor_job(self._calculate_diff)

        # Update state
        await self.hass.async_add_executor_job(self._set_state)
        return

    def _set_state(self) -> None:
        num_reached: bool = False
        pct_reached: bool = False
        if self._min_change_amount > 0:
            num_reached = abs(self._change_amount) >= abs(self._min_change_amount)
        if self._min_change_pct > 0:
            pct_reached = abs(self._change_percent) >= abs(self._min_change_pct)
        if not self._require_both and (num_reached or pct_reached):
            self._state = self._validate_direction()
        elif self._require_both and num_reached and pct_reached:
            self._state = self._validate_direction()
        else:
            self._state = False
        if self._invert:
            self._state = not self._state

    def _validate_direction(self) -> bool:
        """
        Return the new state after checking for directionality.

        Assume True since first check already passed.
        Switch to False if we require a direction and the direction isn't met.
        """
        state: bool = True
        if self._positive_only:
            if self._change_amount < 0:
                state = False
        elif self._negative_only:
            if self._change_amount > 0:
                state = False
        return state

    def _calculate_diff(self) -> None:
        """Compute the diff between the current samples and the trailing samples.

        This need run inside executor.
        """
        trailing_sample_values = np.array([s for _, s in self.trailing_samples])
        sample_values = np.array([s for _, s in self.samples])
        self._trailing_avg = np.mean(a=trailing_sample_values)
        self._sample_avg = np.mean(a=sample_values)
        self._change_amount = self._sample_avg - self._trailing_avg
        self._change_percent = (self._change_amount / self._trailing_avg) * 100

    def _trim_trailing_samples(self) -> None:
        trailing_cuttoff = utcnow().timestamp() - self._trailing_sample_duration
        while self.trailing_samples and self.trailing_samples[0][0] < trailing_cuttoff:
            self.trailing_samples.popleft()

    def _trim_samples(self) -> None:
        cutoff = utcnow().timestamp() - self._sample_duration
        print(cutoff)
        while self.samples and self.samples[0][0] < cutoff:
            self.samples.popleft()
