"""Support for Tibber binary sensors."""

from __future__ import annotations

from datetime import timedelta
import logging

import tibber
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Poll every 30 seconds to check phase imbalance sensor value
SCAN_INTERVAL = timedelta(seconds=30)

# Default threshold for phase imbalance alarm (in percentage)
DEFAULT_THRESHOLD = 20.0

# Service to set threshold
SERVICE_SET_THRESHOLD = "set_phase_imbalance_threshold"

SET_THRESHOLD_SCHEMA = vol.Schema(
    {
        vol.Required("entity_id"): cv.entity_id,
        vol.Required("threshold"): vol.All(
            vol.Coerce(float), vol.Range(min=0, max=100)
        ),
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tibber binary sensors (phase imbalance alarm)."""
    _LOGGER.info("Setting up Tibber binary_sensor platform")

    tibber_connection = hass.data[DOMAIN]
    entity_registry = er.async_get(hass)
    entities: list[TibberPhaseImbalanceAlarmBinarySensor] = []

    # Get all homes (including those without real-time data, for testing)
    homes = tibber_connection.get_homes(only_active=False)
    _LOGGER.info("Found %s Tibber homes", len(homes))

    for home in homes:
        _LOGGER.info(
            "Processing home %s: has_real_time=%s",
            home.home_id,
            home.has_real_time_consumption,
        )

        # NOTE: If you later want to restrict to homes with real-time data,
        # uncomment the block below.
        # if not home.has_real_time_consumption:
        #     _LOGGER.info("Home %s has no real-time data, skipping", home.home_id)
        #     continue

        # Find the corresponding phase imbalance percentage sensor
        phase_sensor_unique_id = f"{home.home_id}_rt_phase_imbalance_percent"
        phase_sensor_entity_id = entity_registry.async_get_entity_id(
            "sensor",
            DOMAIN,
            phase_sensor_unique_id,
        )

        _LOGGER.info(
            "Looking for source sensor with unique_id: %s, found entity_id: %s",
            phase_sensor_unique_id,
            phase_sensor_entity_id,
        )

        entity = TibberPhaseImbalanceAlarmBinarySensor(
            tibber_home=home,
            source_entity_id=phase_sensor_entity_id,
        )
        entities.append(entity)
        _LOGGER.info(
            "Created binary_sensor with unique_id: %s",
            entity.unique_id,
        )

    if entities:
        async_add_entities(entities)
        _LOGGER.info(
            "Added %s phase imbalance alarm binary sensors",
            len(entities),
        )
    else:
        _LOGGER.warning("No Tibber phase imbalance alarm binary sensors were created")

    # Register service to set threshold dynamically
    async def handle_set_threshold(call: ServiceCall) -> None:
        """Handle the service call to set threshold."""
        entity_id = call.data["entity_id"]
        threshold = call.data["threshold"]

        _LOGGER.info(
            "Service called: set threshold to %s for %s",
            threshold,
            entity_id,
        )

        # Find the entity
        for entity in entities:
            if entity.entity_id == entity_id:
                entity.set_threshold(threshold)
                await entity.async_update_ha_state(force_refresh=True)
                _LOGGER.info(
                    "Threshold updated to %s for %s",
                    threshold,
                    entity_id,
                )
                break

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_THRESHOLD,
        handle_set_threshold,
        schema=SET_THRESHOLD_SCHEMA,
    )
    _LOGGER.info("Registered service: tibber.set_phase_imbalance_threshold")


class TibberPhaseImbalanceAlarmBinarySensor(BinarySensorEntity):
    """Binary sensor: alarm when phase imbalance exceeds threshold.

    This sensor monitors the phase imbalance percentage sensor and
    triggers an alarm when the value exceeds the configured threshold.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "phase_imbalance_alarm"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(
        self,
        tibber_home: tibber.TibberHome,
        source_entity_id: str | None,
    ) -> None:
        """Initialize the phase imbalance alarm binary sensor."""
        self._tibber_home = tibber_home
        self._home_id = tibber_home.home_id

        # Try to get home name safely
        try:
            self._home_name = tibber_home.name or f"Home {tibber_home.home_id}"
        except (AttributeError, KeyError):
            self._home_name = f"Home {tibber_home.home_id}"

        self._model = "Tibber Pulse"
        self._device_name = f"{self._model} {self._home_name}"
        self._attr_unique_id = f"{self._home_id}_rt_phase_imbalance_alarm"

        # Entity ID of the phase imbalance percentage sensor we're monitoring
        self._source_entity_id: str | None = source_entity_id

        # Threshold value (default 20%, can be changed via service)
        self._threshold_percent: float = DEFAULT_THRESHOLD

        # Extra attributes visible in frontend
        self._attr_extra_state_attributes = {
            "threshold_percent": self._threshold_percent,
            "phase_imbalance_percent": None,
            "source_entity_id": self._source_entity_id,
        }

        _LOGGER.info(
            "Initialized binary_sensor: unique_id=%s, source=%s",
            self._attr_unique_id,
            self._source_entity_id,
        )

    def set_threshold(self, threshold: float) -> None:
        """Set a new threshold value."""
        _LOGGER.info(
            "Setting threshold to %s for %s",
            threshold,
            self.entity_id,
        )
        self._threshold_percent = threshold
        self._attr_extra_state_attributes["threshold_percent"] = threshold

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device_info of the device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._home_id)},
            name=self._home_name,
            manufacturer="Tibber",
            model=self._model,
        )

    @property
    def should_poll(self) -> bool:
        """Enable polling to check the source sensor state."""
        return True

    async def async_update(self) -> None:
        """Update the alarm state based on phase imbalance percent."""
        # Try to find the source entity if not found during init
        if self._source_entity_id is None and self.hass is not None:
            entity_registry = er.async_get(self.hass)
            phase_sensor_unique_id = f"{self._home_id}_rt_phase_imbalance_percent"
            self._source_entity_id = entity_registry.async_get_entity_id(
                "sensor",
                DOMAIN,
                phase_sensor_unique_id,
            )
            self._attr_extra_state_attributes["source_entity_id"] = (
                self._source_entity_id
            )
            _LOGGER.debug(
                "Retried finding source sensor: %s",
                self._source_entity_id,
            )

        # If still not found, mark as unavailable
        if not self._source_entity_id or self.hass is None:
            _LOGGER.debug(
                "Source sensor not found for %s, marking as unavailable",
                self.entity_id,
            )
            self._attr_is_on = False
            self._attr_extra_state_attributes["phase_imbalance_percent"] = None
            return

        # Get the current state of the phase imbalance sensor
        state_obj = self.hass.states.get(self._source_entity_id)
        if state_obj is None:
            _LOGGER.debug(
                "Source sensor %s has no state",
                self._source_entity_id,
            )
            self._attr_is_on = False
            self._attr_extra_state_attributes["phase_imbalance_percent"] = None
            return

        # Handle unavailable/unknown/non-numeric states
        try:
            value = float(state_obj.state)
        except (TypeError, ValueError):
            _LOGGER.debug(
                "Source sensor %s has non-numeric state: %s",
                self._source_entity_id,
                state_obj.state,
            )
            self._attr_is_on = False
            self._attr_extra_state_attributes["phase_imbalance_percent"] = None
            return

        # Core logic: trigger alarm if value exceeds threshold
        self._attr_is_on = value > self._threshold_percent
        self._attr_extra_state_attributes["phase_imbalance_percent"] = value

        _LOGGER.debug(
            "Updated %s: value=%s, threshold=%s, alarm=%s",
            self.entity_id,
            value,
            self._threshold_percent,
            self._attr_is_on,
        )
