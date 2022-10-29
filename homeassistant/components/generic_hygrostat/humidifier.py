"""Adds support for generic hygrostat units."""
from __future__ import annotations

import asyncio
import logging

from homeassistant.components.humidifier import (
    ATTR_HUMIDITY,
    MODE_AWAY,
    MODE_NORMAL,
    PLATFORM_SCHEMA,
    HumidifierDeviceClass,
    HumidifierEntity,
    HumidifierEntityFeature,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_MODE,
    CONF_NAME,
    EVENT_HOMEASSISTANT_START,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import DOMAIN as HA_DOMAIN, HomeAssistant, callback
from homeassistant.helpers import condition
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_track_state_change,
    async_track_time_interval,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import (
    CONF_AWAY_FIXED,
    CONF_AWAY_HUMIDITY,
    CONF_DEVICE_CLASS,
    CONF_DRY_TOLERANCE,
    CONF_HUMIDIFIER,
    CONF_INITIAL_STATE,
    CONF_KEEP_ALIVE,
    CONF_MAX_HUMIDITY,
    CONF_MIN_DUR,
    CONF_MIN_HUMIDITY,
    CONF_SENSOR,
    CONF_STALE_DURATION,
    CONF_TARGET_HUMIDITY,
    CONF_WET_TOLERANCE,
    HYGROSTAT_SCHEMA,
)

_LOGGER = logging.getLogger(__name__)

ATTR_SAVED_HUMIDITY = "saved_humidity"


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(HYGROSTAT_SCHEMA.schema)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the generic hygrostat platform."""
    if discovery_info:
        config = discovery_info
    name = config[CONF_NAME]
    switch_entity_id = config[CONF_HUMIDIFIER]
    sensor_entity_id = config[CONF_SENSOR]
    min_humidity = config.get(CONF_MIN_HUMIDITY)
    max_humidity = config.get(CONF_MAX_HUMIDITY)
    target_humidity = config.get(CONF_TARGET_HUMIDITY)
    device_class = config.get(CONF_DEVICE_CLASS)
    min_cycle_duration = config.get(CONF_MIN_DUR)
    sensor_stale_duration = config.get(CONF_STALE_DURATION)
    dry_tolerance = config[CONF_DRY_TOLERANCE]
    wet_tolerance = config[CONF_WET_TOLERANCE]
    keep_alive = config.get(CONF_KEEP_ALIVE)
    initial_state = config.get(CONF_INITIAL_STATE)
    away_humidity = config.get(CONF_AWAY_HUMIDITY)
    away_fixed = config.get(CONF_AWAY_FIXED)

    async_add_entities(
        [
            GenericHygrostat(
                name,
                switch_entity_id,
                sensor_entity_id,
                min_humidity,
                max_humidity,
                target_humidity,
                device_class,
                min_cycle_duration,
                dry_tolerance,
                wet_tolerance,
                keep_alive,
                initial_state,
                away_humidity,
                away_fixed,
                sensor_stale_duration,
            )
        ]
    )


class GenericHygrostat(HumidifierEntity, RestoreEntity):
    """Representation of a Generic Hygrostat device."""

    _attr_should_poll = False

    def __init__(
        self,
        name,
        switch_entity_id,
        sensor_entity_id,
        min_humidity,
        max_humidity,
        target_humidity,
        device_class,
        min_cycle_duration,
        dry_tolerance,
        wet_tolerance,
        keep_alive,
        initial_state,
        away_humidity,
        away_fixed,
        sensor_stale_duration,
    ):
        """Initialize the hygrostat."""
        self._name = name
        self._switch_entity_id = switch_entity_id
        self._sensor_entity_id = sensor_entity_id
        self._device_class = device_class
        self._min_cycle_duration = min_cycle_duration
        self._dry_tolerance = dry_tolerance
        self._wet_tolerance = wet_tolerance
        self._keep_alive = keep_alive
        self._state = initial_state
        self._saved_target_humidity = away_humidity or target_humidity
        self._active = False
        self._cur_humidity = None
        self._humidity_lock = asyncio.Lock()
        self._min_humidity = min_humidity
        self._max_humidity = max_humidity
        self._target_humidity = target_humidity
        self._attr_supported_features = 0
        if away_humidity:
            self._attr_supported_features |= HumidifierEntityFeature.MODES
        self._away_humidity = away_humidity
        self._away_fixed = away_fixed
        self._sensor_stale_duration = sensor_stale_duration
        self._remove_stale_tracking = None
        self._is_away = False
        if not self._device_class:
            self._device_class = HumidifierDeviceClass.HUMIDIFIER

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()

        # Add listener
        async_track_state_change(
            self.hass, self._sensor_entity_id, self._async_sensor_changed
        )
        async_track_state_change(
            self.hass, self._switch_entity_id, self._async_switch_changed
        )

        if self._keep_alive:
            async_track_time_interval(self.hass, self._async_operate, self._keep_alive)

        async def _async_startup(event):
            """Init on startup."""
            sensor_state = self.hass.states.get(self._sensor_entity_id)
            await self._async_sensor_changed(self._sensor_entity_id, None, sensor_state)

        self.hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, _async_startup)

        if (old_state := await self.async_get_last_state()) is not None:
            if old_state.attributes.get(ATTR_MODE) == MODE_AWAY:
                self._is_away = True
                self._saved_target_humidity = self._target_humidity
                self._target_humidity = self._away_humidity or self._target_humidity
            if old_state.attributes.get(ATTR_HUMIDITY):
                self._target_humidity = int(old_state.attributes[ATTR_HUMIDITY])
            if old_state.attributes.get(ATTR_SAVED_HUMIDITY):
                self._saved_target_humidity = int(
                    old_state.attributes[ATTR_SAVED_HUMIDITY]
                )
            if old_state.state:
                self._state = old_state.state == STATE_ON
        if self._target_humidity is None:
            if self._device_class == HumidifierDeviceClass.HUMIDIFIER:
                self._target_humidity = self.min_humidity
            else:
                self._target_humidity = self.max_humidity
            _LOGGER.warning(
                "No previously saved humidity, setting to %s", self._target_humidity
            )
        if self._state is None:
            self._state = False

        await _async_startup(None)  # init the sensor

    @property
    def available(self):
        """Return True if entity is available."""
        return self._active

    @property
    def extra_state_attributes(self):
        """Return the optional state attributes."""
        if self._saved_target_humidity:
            return {ATTR_SAVED_HUMIDITY: self._saved_target_humidity}
        return None

    @property
    def name(self):
        """Return the name of the hygrostat."""
        return self._name

    @property
    def is_on(self):
        """Return true if the hygrostat is on."""
        return self._state

    @property
    def target_humidity(self):
        """Return the humidity we try to reach."""
        return self._target_humidity

    @property
    def mode(self):
        """Return the current mode."""
        if self._away_humidity is None:
            return None
        if self._is_away:
            return MODE_AWAY
        return MODE_NORMAL

    @property
    def available_modes(self):
        """Return a list of available modes."""
        if self._away_humidity:
            return [MODE_NORMAL, MODE_AWAY]
        return None

    @property
    def device_class(self):
        """Return the device class of the humidifier."""
        return self._device_class

    async def async_turn_on(self, **kwargs):
        """Turn hygrostat on."""
        if not self._active:
            return
        self._state = True
        await self._async_operate(force=True)
        await self.async_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn hygrostat off."""
        if not self._active:
            return
        self._state = False
        if self._is_device_active:
            await self._async_device_turn_off()
        await self.async_update_ha_state()

    async def async_set_humidity(self, humidity: int):
        """Set new target humidity."""
        if humidity is None:
            return

        if self._is_away and self._away_fixed:
            self._saved_target_humidity = humidity
            await self.async_update_ha_state()
            return

        self._target_humidity = humidity
        await self._async_operate()
        await self.async_update_ha_state()

    @property
    def min_humidity(self):
        """Return the minimum humidity."""
        if self._min_humidity:
            return self._min_humidity

        # get default humidity from super class
        return super().min_humidity

    @property
    def max_humidity(self):
        """Return the maximum humidity."""
        if self._max_humidity:
            return self._max_humidity

        # Get default humidity from super class
        return super().max_humidity

    async def _async_sensor_changed(self, entity_id, old_state, new_state):
        """Handle ambient humidity changes."""
        if new_state is None:
            return

        if self._sensor_stale_duration:
            if self._remove_stale_tracking:
                self._remove_stale_tracking()
            self._remove_stale_tracking = async_track_time_interval(
                self.hass,
                self._async_sensor_not_responding,
                self._sensor_stale_duration,
            )

        await self._async_update_humidity(new_state.state)
        await self._async_operate()
        await self.async_update_ha_state()

    async def _async_sensor_not_responding(self, now=None):
        """Handle sensor stale event."""

        _LOGGER.debug(
            "Sensor has not been updated for %s",
            now - self.hass.states.get(self._sensor_entity_id).last_updated,
        )
        _LOGGER.warning("Sensor is stalled, call the emergency stop")
        await self._async_update_humidity("Stalled")

    @callback
    def _async_switch_changed(self, entity_id, old_state, new_state):
        """Handle humidifier switch state changes."""
        if new_state is None:
            return
        self.async_schedule_update_ha_state()

    async def _async_update_humidity(self, humidity):
        """Update hygrostat with latest state from sensor."""
        try:
            self._cur_humidity = float(humidity)
        except ValueError as ex:
            _LOGGER.warning("Unable to update from sensor: %s", ex)
            self._cur_humidity = None
            self._active = False
            if self._is_device_active:
                await self._async_device_turn_off()

    async def _async_operate(self, time=None, force=False):
        """Check if we need to turn humidifying on or off."""
        async with self._humidity_lock:
            if not self._active and None not in (
                self._cur_humidity,
                self._target_humidity,
            ):
                self._active = True
                force = True
                _LOGGER.info(
                    "Obtained current and target humidity. "
                    "Generic hygrostat active. %s, %s",
                    self._cur_humidity,
                    self._target_humidity,
                )

            if not self._active or not self._state:
                return

            if not force and time is None:
                # If the `force` argument is True, we
                # ignore `min_cycle_duration`.
                # If the `time` argument is not none, we were invoked for
                # keep-alive purposes, and `min_cycle_duration` is irrelevant.
                if self._min_cycle_duration:
                    if self._is_device_active:
                        current_state = STATE_ON
                    else:
                        current_state = STATE_OFF
                    long_enough = condition.state(
                        self.hass,
                        self._switch_entity_id,
                        current_state,
                        self._min_cycle_duration,
                    )
                    if not long_enough:
                        return

            if force:
                # Ignore the tolerance when switched on manually
                dry_tolerance = 0
                wet_tolerance = 0
            else:
                dry_tolerance = self._dry_tolerance
                wet_tolerance = self._wet_tolerance

            too_dry = self._target_humidity - self._cur_humidity >= dry_tolerance
            too_wet = self._cur_humidity - self._target_humidity >= wet_tolerance
            if self._is_device_active:
                if (
                    self._device_class == HumidifierDeviceClass.HUMIDIFIER and too_wet
                ) or (
                    self._device_class == HumidifierDeviceClass.DEHUMIDIFIER and too_dry
                ):
                    _LOGGER.info("Turning off humidifier %s", self._switch_entity_id)
                    await self._async_device_turn_off()
                elif time is not None:
                    # The time argument is passed only in keep-alive case
                    await self._async_device_turn_on()
            else:
                if (
                    self._device_class == HumidifierDeviceClass.HUMIDIFIER and too_dry
                ) or (
                    self._device_class == HumidifierDeviceClass.DEHUMIDIFIER and too_wet
                ):
                    _LOGGER.info("Turning on humidifier %s", self._switch_entity_id)
                    await self._async_device_turn_on()
                elif time is not None:
                    # The time argument is passed only in keep-alive case
                    await self._async_device_turn_off()

    @property
    def _is_device_active(self):
        """If the toggleable device is currently active."""
        return self.hass.states.is_state(self._switch_entity_id, STATE_ON)

    async def _async_device_turn_on(self):
        """Turn humidifier toggleable device on."""
        data = {ATTR_ENTITY_ID: self._switch_entity_id}
        await self.hass.services.async_call(HA_DOMAIN, SERVICE_TURN_ON, data)

    async def _async_device_turn_off(self):
        """Turn humidifier toggleable device off."""
        data = {ATTR_ENTITY_ID: self._switch_entity_id}
        await self.hass.services.async_call(HA_DOMAIN, SERVICE_TURN_OFF, data)

    async def async_set_mode(self, mode: str):
        """Set new mode.

        This method must be run in the event loop and returns a coroutine.
        """
        if self._away_humidity is None:
            return
        if mode == MODE_AWAY and not self._is_away:
            self._is_away = True
            if not self._saved_target_humidity:
                self._saved_target_humidity = self._away_humidity
            self._saved_target_humidity, self._target_humidity = (
                self._target_humidity,
                self._saved_target_humidity,
            )
            await self._async_operate(force=True)
        elif mode == MODE_NORMAL and self._is_away:
            self._is_away = False
            self._saved_target_humidity, self._target_humidity = (
                self._target_humidity,
                self._saved_target_humidity,
            )
            await self._async_operate(force=True)

        await self.async_update_ha_state()
