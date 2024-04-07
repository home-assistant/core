"""Support for package tracking sensors from 17track.net."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import persistent_notification
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType, StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import SeventeenTrackCoordinator
from .const import (
    ATTR_PACKAGES,
    ATTRIBUTION,
    CONF_SHOW_ARCHIVED,
    CONF_SHOW_DELIVERED,
    DOMAIN,
    ENTITY_ID_TEMPLATE,
    LOGGER,
    NOTIFICATION_DELIVERED_MESSAGE,
    NOTIFICATION_DELIVERED_TITLE,
    UNIQUE_ID_TEMPLATE,
    VALUE_DELIVERED,
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SHOW_ARCHIVED, default=False): cv.boolean,
        vol.Optional(CONF_SHOW_DELIVERED, default=False): cv.boolean,
    }
)

ISSUE_PLACEHOLDER = {"url": "/config/integrations/dashboard/add?domain=seventeentrack"}


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Initialize 17Track import from config."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=config
    )
    if (
        result["type"] == FlowResultType.CREATE_ENTRY
        or result["reason"] == "already_configured"
    ):
        async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            is_fixable=False,
            breaks_in_ha_version="2024.10.0",
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "17Track",
            },
        )
    else:
        async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{result['reason']}",
            breaks_in_ha_version="2024.10.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_{result['reason']}",
            translation_placeholders=ISSUE_PLACEHOLDER,
        )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a 17Track sensor entry."""

    coordinator: SeventeenTrackCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    @callback
    def _async_create_remove_entities():
        for package in coordinator.data.old_packages:
            remove_entity(hass, coordinator.account_id, package.tracking_number)

        async_add_entities(
            SeventeenTrackPackageSensor(coordinator, t_number)
            for t_number, p_data in coordinator.data.new_packages.items()
            if not (not coordinator.show_delivered and p_data.status == "Delivered")
        )

        for tracking_number, package_data in coordinator.data.new_packages.items():
            if (
                package_data.status == VALUE_DELIVERED
                and not coordinator.show_delivered
            ):
                notify_delivered(
                    hass,
                    package_data.friendly_name,
                    tracking_number,
                )

    async_add_entities(
        SeventeenTrackSummarySensor(status, coordinator)
        for status in coordinator.data.summary
    )

    _async_create_remove_entities()

    config_entry.async_on_unload(
        coordinator.async_add_listener(_async_create_remove_entities)
    )


class SeventeenTrackSummarySensor(
    CoordinatorEntity[SeventeenTrackCoordinator], SensorEntity
):
    """Define a summary sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_icon = "mdi:package"
    _attr_native_unit_of_measurement = "packages"

    def __init__(
        self,
        status: str,
        coordinator: SeventeenTrackCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._status = status
        self._attr_extra_state_attributes = {}
        self._attr_name = f"Seventeentrack Packages {self._status}"
        self._attr_unique_id = f"summary_{coordinator.account_id}_{self._status}"

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        return self.coordinator.data.summary[self._status]["quantity"] is not None

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.coordinator.data.summary[self._status]["quantity"]

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        return {ATTR_PACKAGES: self.coordinator.data.summary[self._status]["packages"]}


class SeventeenTrackPackageSensor(
    CoordinatorEntity[SeventeenTrackCoordinator], SensorEntity
):
    """Define an individual package sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_icon = "mdi:package"

    def __init__(
        self,
        coordinator: SeventeenTrackCoordinator,
        tracking_number: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_extra_state_attributes = {}
        self._tracking_number = tracking_number
        self.entity_id = ENTITY_ID_TEMPLATE.format(tracking_number)
        self._attr_unique_id = UNIQUE_ID_TEMPLATE.format(
            coordinator.account_id, tracking_number
        )

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        return self._tracking_number in self.coordinator.data.current_packages

    @property
    def name(self) -> str:
        """Return the name."""
        package_data = self.coordinator.data.current_packages.get(
            self._tracking_number, {}
        )
        package = package_data.get("package")
        if package is None or not (name := package.friendly_name):
            name = self._tracking_number
        return f"Seventeentrack Package: {name}"

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        package_data = self.coordinator.data.current_packages.get(
            self._tracking_number, {}
        )
        return package_data["package"].status

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        package_data = self.coordinator.data.current_packages.get(
            self._tracking_number, {}
        )
        return package_data["extra"]


def remove_entity(hass: HomeAssistant, account_id: str, tracking_number: str) -> bool:
    """Remove entity itself."""
    reg = er.async_get(hass)
    entity_id = reg.async_get_entity_id(
        "sensor",
        "seventeentrack",
        UNIQUE_ID_TEMPLATE.format(account_id, tracking_number),
    )
    if entity_id:
        reg.async_remove(entity_id)
        return True
    return False


def notify_delivered(hass: HomeAssistant, friendly_name: str, tracking_number: str):
    """Notify when package is delivered."""
    LOGGER.info("Package delivered: %s", tracking_number)

    identification = friendly_name if friendly_name else tracking_number
    message = NOTIFICATION_DELIVERED_MESSAGE.format(identification, tracking_number)
    title = NOTIFICATION_DELIVERED_TITLE.format(identification)
    notification_id = NOTIFICATION_DELIVERED_TITLE.format(tracking_number)

    persistent_notification.create(
        hass, message, title=title, notification_id=notification_id
    )
