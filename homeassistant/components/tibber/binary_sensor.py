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
            vol.Coerce(float),
            vol.Range(min=0, max=100),
        ),
    }
)


class TibberPhaseImbalanceAlarmBinarySensor(BinarySensorEntity):
    """Binary sensor: alarm when phase imbalance exceeds threshold."""

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
        self._home_name = getattr(tibber_home, "name", None) or f"Home {self._home_id}"

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

        _LOGGER.debug(
            "Initialized Tibber phase imbalance alarm: unique_id=%s, source=%s",
            self._attr_unique_id,
            self._source_entity_id,
        )

    def set_threshold(self, threshold: float) -> None:
        """Set a new threshold value."""
        _LOGGER.debug(
            "Setting threshold to %s for entity %s",
            threshold,
            self.entity_id,
        )
        self._threshold_percent = threshold
        self._attr_extra_state_attributes["threshold_percent"] = threshold

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for this sensor."""
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
        alarm_on = False
        phase_value: float | None = None

        hass = self.hass

        if hass is not None:
            # Ensure we have a source entity id; try to resolve it from the registry if missing
            if self._source_entity_id is None:
                entity_registry = er.async_get(hass)
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
                    "Retried finding source sensor for %s: %s",
                    self._home_id,
                    self._source_entity_id,
                )

            source_entity_id = self._source_entity_id

            if source_entity_id is not None:
                state_obj = hass.states.get(source_entity_id)
                if state_obj is not None:
                    try:
                        value = float(state_obj.state)
                    except (TypeError, ValueError):
                        _LOGGER.debug(
                            "Source sensor %s has non-numeric state: %s",
                            source_entity_id,
                            state_obj.state,
                        )
                    else:
                        phase_value = value
                        alarm_on = value > self._threshold_percent
                else:
                    _LOGGER.debug(
                        "Source sensor %s has no state",
                        source_entity_id,
                    )
            else:
                _LOGGER.debug(
                    "Source sensor not found for %s; treating as unavailable",
                    self.entity_id,
                )
        else:
            _LOGGER.debug(
                "Home Assistant instance is not available for %s; treating as unavailable",
                self.entity_id,
            )

        # Apply computed values to the entity
        self._attr_is_on = alarm_on
        self._attr_extra_state_attributes["phase_imbalance_percent"] = phase_value


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Tibber binary sensors (phase imbalance alarm)."""

    _LOGGER.debug("Setting up Tibber binary_sensor platform")

    if DOMAIN not in hass.data:
        _LOGGER.error(
            "Tibber domain not found in hass.data; cannot set up binary sensors",
        )
        return

    tibber_connection = hass.data[DOMAIN]
    entity_registry = er.async_get(hass)
    entities: list[TibberPhaseImbalanceAlarmBinarySensor] = []

    homes = tibber_connection.get_homes(only_active=False)
    _LOGGER.debug("Found %d Tibber homes", len(homes))

    for home in homes:
        _LOGGER.debug(
            "Processing Tibber home %s (has_real_time=%s)",
            home.home_id,
            home.has_real_time_consumption,
        )

        # If you want to require realtime data, uncomment this:
        # if not home.has_real_time_consumption:
        #     _LOGGER.debug("Home %s has no realtime data; skipping", home.home_id)
        #     continue

        phase_sensor_unique_id = f"{home.home_id}_rt_phase_imbalance_percent"
        phase_sensor_entity_id = entity_registry.async_get_entity_id(
            "sensor",
            DOMAIN,
            phase_sensor_unique_id,
        )

        _LOGGER.debug(
            "Phase imbalance sensor unique_id=%s -> entity_id=%s",
            phase_sensor_unique_id,
            phase_sensor_entity_id,
        )

        entity = TibberPhaseImbalanceAlarmBinarySensor(
            tibber_home=home,
            source_entity_id=phase_sensor_entity_id,
        )
        entities.append(entity)

    _LOGGER.debug(
        "Total Tibber phase imbalance alarm entities to add: %d",
        len(entities),
    )

    if entities:
        async_add_entities(entities)
    else:
        _LOGGER.warning(
            "No Tibber phase imbalance alarm binary sensors were created; "
            "entities list is empty",
        )

    async def handle_set_threshold(call: ServiceCall) -> None:
        """Handle the service call to set threshold."""
        entity_id = call.data["entity_id"]
        threshold = call.data["threshold"]

        _LOGGER.debug(
            "Service %s called: set threshold=%s for entity_id=%s",
            SERVICE_SET_THRESHOLD,
            threshold,
            entity_id,
        )

        for entity in entities:
            # entity.entity_id is only set after being added to HA,
            # so we check both entity_id and unique_id for convenience.
            if entity_id in (entity.entity_id, entity.unique_id):
                entity.set_threshold(threshold)
                await entity.async_update_ha_state(force_refresh=True)
                _LOGGER.debug(
                    "Threshold updated to %s for entity_id=%s",
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
    _LOGGER.debug(
        "Registered Tibber service %s.%s",
        DOMAIN,
        SERVICE_SET_THRESHOLD,
    )
