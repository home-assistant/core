"""Support for package tracking sensors from 17track.net."""

from __future__ import annotations

from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_FRIENDLY_NAME, ATTR_LOCATION
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SeventeenTrackCoordinator
from .const import (
    ATTR_DESTINATION_COUNTRY,
    ATTR_INFO_TEXT,
    ATTR_ORIGIN_COUNTRY,
    ATTR_PACKAGE_TYPE,
    ATTR_PACKAGES,
    ATTR_STATUS,
    ATTR_TIMESTAMP,
    ATTR_TRACKING_INFO_LANGUAGE,
    ATTR_TRACKING_NUMBER,
    ATTRIBUTION,
    DEPRECATED_KEY,
    DOMAIN,
    LOGGER,
    NOTIFICATION_DELIVERED_MESSAGE,
    NOTIFICATION_DELIVERED_TITLE,
    UNIQUE_ID_TEMPLATE,
    VALUE_DELIVERED,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a 17Track sensor entry."""

    coordinator: SeventeenTrackCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    previous_tracking_numbers: set[str] = set()

    # This has been deprecated in 2024.8, will be removed in 2025.2
    @callback
    def _async_create_remove_entities():
        if config_entry.data.get(DEPRECATED_KEY):
            remove_packages(hass, coordinator.account_id, previous_tracking_numbers)
            return
        live_tracking_numbers = set(coordinator.data.live_packages.keys())

        new_tracking_numbers = live_tracking_numbers - previous_tracking_numbers
        old_tracking_numbers = previous_tracking_numbers - live_tracking_numbers

        previous_tracking_numbers.update(live_tracking_numbers)

        packages_to_add = [
            coordinator.data.live_packages[tracking_number]
            for tracking_number in new_tracking_numbers
        ]

        for package_data in coordinator.data.live_packages.values():
            if (
                package_data.status == VALUE_DELIVERED
                and not coordinator.show_delivered
            ):
                old_tracking_numbers.add(package_data.tracking_number)
                notify_delivered(
                    hass,
                    package_data.friendly_name,
                    package_data.tracking_number,
                )

        remove_packages(hass, coordinator.account_id, old_tracking_numbers)

        async_add_entities(
            SeventeenTrackPackageSensor(
                coordinator,
                package_data.tracking_number,
            )
            for package_data in packages_to_add
            if not (
                not coordinator.show_delivered and package_data.status == "Delivered"
            )
        )

    async_add_entities(
        SeventeenTrackSummarySensor(status, coordinator)
        for status, summary_data in coordinator.data.summary.items()
    )

    if not config_entry.data.get(DEPRECATED_KEY):
        deprecate_sensor_issue(hass, config_entry.entry_id)
        _async_create_remove_entities()
        config_entry.async_on_unload(
            coordinator.async_add_listener(_async_create_remove_entities)
        )


class SeventeenTrackSensor(CoordinatorEntity[SeventeenTrackCoordinator], SensorEntity):
    """Define a 17Track sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(self, coordinator: SeventeenTrackCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.account_id)},
            entry_type=DeviceEntryType.SERVICE,
            name="17Track",
        )


class SeventeenTrackSummarySensor(SeventeenTrackSensor):
    """Define a summary sensor."""

    _attr_native_unit_of_measurement = "packages"

    def __init__(
        self,
        status: str,
        coordinator: SeventeenTrackCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._status = status
        self._attr_translation_key = status
        self._attr_unique_id = f"summary_{coordinator.account_id}_{status}"

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        return self._status in self.coordinator.data.summary

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.coordinator.data.summary[self._status]["quantity"]

    # This has been deprecated in 2024.8, will be removed in 2025.2
    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        packages = self.coordinator.data.summary[self._status]["packages"]
        return {
            ATTR_PACKAGES: [
                {
                    ATTR_TRACKING_NUMBER: package.tracking_number,
                    ATTR_LOCATION: package.location,
                    ATTR_STATUS: package.status,
                    ATTR_TIMESTAMP: package.timestamp,
                    ATTR_INFO_TEXT: package.info_text,
                    ATTR_FRIENDLY_NAME: package.friendly_name,
                }
                for package in packages
            ]
        }


# The dynamic package sensors have been replaced by the seventeentrack.get_packages service
class SeventeenTrackPackageSensor(SeventeenTrackSensor):
    """Define an individual package sensor."""

    _attr_translation_key = "package"

    def __init__(
        self,
        coordinator: SeventeenTrackCoordinator,
        tracking_number: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._tracking_number = tracking_number
        self._previous_status = coordinator.data.live_packages[tracking_number].status
        self._attr_unique_id = UNIQUE_ID_TEMPLATE.format(
            coordinator.account_id, tracking_number
        )
        package = coordinator.data.live_packages[tracking_number]
        if not (name := package.friendly_name):
            name = tracking_number
        self._attr_translation_placeholders = {"name": name}

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        return self._tracking_number in self.coordinator.data.live_packages

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        return self.coordinator.data.live_packages[self._tracking_number].status

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        package = self.coordinator.data.live_packages[self._tracking_number]
        return {
            ATTR_DESTINATION_COUNTRY: package.destination_country,
            ATTR_INFO_TEXT: package.info_text,
            ATTR_TIMESTAMP: package.timestamp,
            ATTR_LOCATION: package.location,
            ATTR_ORIGIN_COUNTRY: package.origin_country,
            ATTR_PACKAGE_TYPE: package.package_type,
            ATTR_TRACKING_INFO_LANGUAGE: package.tracking_info_language,
            ATTR_TRACKING_NUMBER: package.tracking_number,
        }


def remove_packages(hass: HomeAssistant, account_id: str, packages: set[str]) -> None:
    """Remove entity itself."""
    reg = er.async_get(hass)
    for package in packages:
        entity_id = reg.async_get_entity_id(
            "sensor",
            "seventeentrack",
            UNIQUE_ID_TEMPLATE.format(account_id, package),
        )
        if entity_id:
            reg.async_remove(entity_id)


def notify_delivered(hass: HomeAssistant, friendly_name: str, tracking_number: str):
    """Notify when package is delivered."""
    LOGGER.debug("Package delivered: %s", tracking_number)

    identification = friendly_name if friendly_name else tracking_number
    message = NOTIFICATION_DELIVERED_MESSAGE.format(identification, tracking_number)
    title = NOTIFICATION_DELIVERED_TITLE.format(identification)
    notification_id = NOTIFICATION_DELIVERED_TITLE.format(tracking_number)

    persistent_notification.create(
        hass, message, title=title, notification_id=notification_id
    )


@callback
def deprecate_sensor_issue(hass: HomeAssistant, entry_id: str) -> None:
    """Ensure an issue is registered."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"deprecate_sensor_{entry_id}",
        breaks_in_ha_version="2025.2.0",
        issue_domain=DOMAIN,
        is_fixable=True,
        is_persistent=True,
        translation_key="deprecate_sensor",
        severity=ir.IssueSeverity.WARNING,
        data={"entry_id": entry_id},
    )
