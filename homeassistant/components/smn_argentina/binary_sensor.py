"""Binary sensor platform for SMN weather alerts."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ALERT_EVENT_ICONS, ALERT_EVENT_MAP, ALERT_LEVEL_MAP, DOMAIN
from .coordinator import ArgentinaSMNDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Event types for Home Assistant events
EVENT_ALERT_CREATED = f"{DOMAIN}_alert_created"
EVENT_ALERT_UPDATED = f"{DOMAIN}_alert_updated"
EVENT_ALERT_CLEARED = f"{DOMAIN}_alert_cleared"


def _get_alert_details(
    event_id: int, level: int, reports: list[dict[str, Any]]
) -> tuple[str | None, str | None]:
    """Get description and instruction for a specific alert event."""
    for report in reports:
        if report.get("event_id") == event_id:
            levels = report.get("levels", [])
            for level_data in levels:
                if level_data.get("level") == level:
                    return (
                        level_data.get("description"),
                        level_data.get("instruction"),
                    )
    return None, None


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry[ArgentinaSMNDataUpdateCoordinator],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SMN binary sensors."""
    coordinator = config_entry.runtime_data

    entities: list[BinarySensorEntity] = []

    # Main alert sensor
    entities.append(SMNAlertSensor(coordinator, config_entry))

    # Individual event type sensors
    for event_id, event_name in ALERT_EVENT_MAP.items():
        entities.append(
            SMNEventAlertSensor(coordinator, config_entry, event_id, event_name)
        )

    # Short-term alert sensor
    entities.append(SMNShortTermAlertSensor(coordinator, config_entry))

    async_add_entities(entities)


class SMNAlertSensor(
    CoordinatorEntity[ArgentinaSMNDataUpdateCoordinator], BinarySensorEntity
):
    """Binary sensor for SMN weather alerts (all types)."""

    _attr_device_class = BinarySensorDeviceClass.SAFETY
    _attr_has_entity_name = True
    _attr_translation_key = "weather_alert"
    _attr_icon = "mdi:alert"

    def __init__(
        self,
        coordinator: ArgentinaSMNDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_unique_id = f"{config_entry.entry_id}_alert"
        self._previous_alerts: set[tuple[int, int]] = set()  # (event_id, level)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        location_id = self.coordinator.data.location_id
        device_info_dict = {
            "identifiers": {(DOMAIN, self._config_entry.entry_id)},
            "name": self._config_entry.data.get(CONF_NAME, "SMN Weather"),
            "manufacturer": "Servicio Meteorológico Nacional",
            "entry_type": DeviceEntryType.SERVICE,
        }

        # Add location_id to configuration_url if available
        if location_id:
            device_info_dict["configuration_url"] = (
                f"https://www.smn.gob.ar/pronostico/?loc={location_id}"
            )

        return DeviceInfo(**device_info_dict)  # type: ignore[typeddict-item]

    @property
    def is_on(self) -> bool:
        """Return True if there are active alerts."""
        if not self.coordinator.data.alerts:
            return False

        warnings = self.coordinator.data.alerts.get("warnings", [])
        if not warnings or len(warnings) == 0:
            return False

        # Check if any event has level > 1
        current_warning = warnings[0]
        events = current_warning.get("events", [])
        return any(event.get("max_level", 1) > 1 for event in events)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if not self.coordinator.data.alerts:
            return {}

        warnings = self.coordinator.data.alerts.get("warnings", [])
        reports = self.coordinator.data.alerts.get("reports", [])

        if not warnings or len(warnings) == 0:
            return {
                "active_alert_count": 0,
                "max_severity": "info",
                "max_level": 1,
            }

        current_warning = warnings[0]
        events = current_warning.get("events", [])

        # Count active alerts and find max severity
        active_alerts = []
        max_level = 1

        for event in events:
            event_level = event.get("max_level", 1)
            if event_level > 1:
                event_id = event.get("id")
                event_name = ALERT_EVENT_MAP.get(event_id, f"unknown_{event_id}")
                level_info = ALERT_LEVEL_MAP.get(event_level, ALERT_LEVEL_MAP[1])

                # Find description from reports
                description, _ = _get_alert_details(event_id, event_level, reports)

                active_alerts.append(
                    {
                        "event_name": event_name,
                        "level_name": level_info["name"],
                        "severity": level_info["severity"],
                        "description": description,
                    }
                )
                max_level = max(max_level, event_level)

        max_severity_info = ALERT_LEVEL_MAP.get(max_level, ALERT_LEVEL_MAP[1])
        alert_summary = ", ".join(
            [f"{a['event_name']} ({a['level_name']})" for a in active_alerts]
        )

        return {
            "active_alert_count": len(active_alerts),
            "max_severity": max_severity_info["severity"],
            "max_level": max_level,
            "alert_summary": alert_summary,
            "active_alerts": active_alerts,
            "area_id": self.coordinator.data.alerts.get("area_id"),
            "updated": self.coordinator.data.alerts.get("updated"),
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Fire events for alert changes
        self._fire_alert_events()
        super()._handle_coordinator_update()

    def _fire_alert_events(self) -> None:
        """Fire Home Assistant events for alert changes."""
        if not self.coordinator.data.alerts:
            return

        warnings = self.coordinator.data.alerts.get("warnings", [])
        if not warnings:
            return

        current_warning = warnings[0]
        events = current_warning.get("events", [])
        reports = self.coordinator.data.alerts.get("reports", [])

        # Build current alerts set
        current_alerts: set[tuple[int, int]] = set()
        for event in events:
            event_id = event.get("id")
            max_level = event.get("max_level", 1)
            if max_level > 1:
                current_alerts.add((event_id, max_level))

        # Find new alerts
        new_alerts = current_alerts - self._previous_alerts
        for event_id, level in new_alerts:
            event_name = ALERT_EVENT_MAP.get(event_id, f"unknown_{event_id}")
            level_info = ALERT_LEVEL_MAP.get(level, ALERT_LEVEL_MAP[1])

            # Find description
            description, _ = _get_alert_details(event_id, level, reports)

            self.hass.bus.fire(
                EVENT_ALERT_CREATED,
                {
                    "event_id": event_id,
                    "event_name": event_name,
                    "level": level,
                    "level_name": level_info["name"],
                    "severity": level_info["severity"],
                    "description": description,
                },
            )
            _LOGGER.info(
                "Alert created: %s (level %d - %s)",
                event_name,
                level,
                level_info["name"],
            )

        # Find updated alerts (level changed)
        updated_alerts = current_alerts & self._previous_alerts
        for event_id, level in updated_alerts:
            # Check if level changed
            old_level = next(
                (lvl for eid, lvl in self._previous_alerts if eid == event_id), None
            )
            if old_level and old_level != level:
                event_name = ALERT_EVENT_MAP.get(event_id, f"unknown_{event_id}")
                level_info = ALERT_LEVEL_MAP.get(level, ALERT_LEVEL_MAP[1])

                self.hass.bus.fire(
                    EVENT_ALERT_UPDATED,
                    {
                        "event_id": event_id,
                        "event_name": event_name,
                        "old_level": old_level,
                        "new_level": level,
                        "level_name": level_info["name"],
                        "severity": level_info["severity"],
                    },
                )
                _LOGGER.info(
                    "Alert updated: %s (level %d → %d)",
                    event_name,
                    old_level,
                    level,
                )

        # Find cleared alerts
        cleared_alerts = self._previous_alerts - current_alerts
        for event_id, level in cleared_alerts:
            event_name = ALERT_EVENT_MAP.get(event_id, f"unknown_{event_id}")

            self.hass.bus.fire(
                EVENT_ALERT_CLEARED,
                {
                    "event_id": event_id,
                    "event_name": event_name,
                    "level": level,
                },
            )
            _LOGGER.info("Alert cleared: %s (level %d)", event_name, level)

        # Update previous alerts
        self._previous_alerts = current_alerts


class SMNEventAlertSensor(
    CoordinatorEntity[ArgentinaSMNDataUpdateCoordinator], BinarySensorEntity
):
    """Binary sensor for specific SMN weather alert type."""

    _attr_device_class = BinarySensorDeviceClass.SAFETY
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ArgentinaSMNDataUpdateCoordinator,
        config_entry: ConfigEntry,
        event_id: int,
        event_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._event_id = event_id
        self._event_name = event_name
        self._attr_unique_id = f"{config_entry.entry_id}_alert_{event_name}"
        self._attr_translation_key = f"alert_{event_name}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        location_id = self.coordinator.data.location_id
        device_info_dict = {
            "identifiers": {(DOMAIN, self._config_entry.entry_id)},
            "name": self._config_entry.data.get(CONF_NAME, "SMN Weather"),
            "manufacturer": "Servicio Meteorológico Nacional",
            "entry_type": DeviceEntryType.SERVICE,
        }

        # Add location_id to configuration_url if available
        if location_id:
            device_info_dict["configuration_url"] = (
                f"https://www.smn.gob.ar/pronostico/?loc={location_id}"
            )

        return DeviceInfo(**device_info_dict)  # type: ignore[typeddict-item]

    @property
    def icon(self) -> str:
        """Return the icon for this alert type."""
        return ALERT_EVENT_ICONS.get(self._event_name, "mdi:alert")

    @property
    def is_on(self) -> bool:
        """Return True if this alert type is active."""
        if not self.coordinator.data.alerts:
            return False

        warnings = self.coordinator.data.alerts.get("warnings", [])
        if not warnings:
            return False

        current_warning = warnings[0]
        events = current_warning.get("events", [])

        for event in events:
            if event.get("id") == self._event_id and event.get("max_level", 1) > 1:
                return True

        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if not self.is_on:
            return {"level": 1, "severity": "info"}

        warnings = self.coordinator.data.alerts.get("warnings", [])
        reports = self.coordinator.data.alerts.get("reports", [])
        current_warning = warnings[0]
        events = current_warning.get("events", [])

        for event in events:
            if event.get("id") == self._event_id:
                level = event.get("max_level", 1)
                level_info = ALERT_LEVEL_MAP.get(level, ALERT_LEVEL_MAP[1])

                # Find description from reports
                description, instruction = _get_alert_details(
                    self._event_id, level, reports
                )

                return {
                    "event_id": self._event_id,
                    "event_name": self._event_name,
                    "level": level,
                    "level_name": level_info["name"],
                    "color": level_info["color"],
                    "severity": level_info["severity"],
                    "date": current_warning.get("date"),
                    "description": description,
                    "instruction": instruction,
                }

        return {"level": 1, "severity": "info"}


class SMNShortTermAlertSensor(
    CoordinatorEntity[ArgentinaSMNDataUpdateCoordinator], BinarySensorEntity
):
    """Binary sensor for SMN short-term severe weather alerts."""

    _attr_device_class = BinarySensorDeviceClass.SAFETY
    _attr_has_entity_name = True
    _attr_translation_key = "short_term_alert"
    _attr_icon = "mdi:alert-circle"

    def __init__(
        self,
        coordinator: ArgentinaSMNDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._attr_unique_id = f"{config_entry.entry_id}_shortterm_alert"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        location_id = self.coordinator.data.location_id
        device_info_dict = {
            "identifiers": {(DOMAIN, self._config_entry.entry_id)},
            "name": self._config_entry.data.get(CONF_NAME, "SMN Weather"),
            "manufacturer": "Servicio Meteorológico Nacional",
            "entry_type": DeviceEntryType.SERVICE,
        }

        # Add location_id to configuration_url if available
        if location_id:
            device_info_dict["configuration_url"] = (
                f"https://www.smn.gob.ar/pronostico/?loc={location_id}"
            )

        return DeviceInfo(**device_info_dict)  # type: ignore[typeddict-item]

    @property
    def is_on(self) -> bool:
        """Return True if there are active short-term alerts."""
        return bool(self.coordinator.data.shortterm_alerts)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if not self.coordinator.data.shortterm_alerts:
            return {"alert_count": 0}

        alerts = self.coordinator.data.shortterm_alerts

        return {
            "alert_count": len(alerts),
            "alerts": [
                {
                    "title": alert.get("title"),
                    "date": alert.get("date"),
                    "end_date": alert.get("end_date"),
                    "severity": alert.get("severity"),
                    "zones": alert.get("zones"),
                    "instructions": alert.get("instructions"),
                    "region": alert.get("region"),
                }
                for alert in alerts
            ],
        }
