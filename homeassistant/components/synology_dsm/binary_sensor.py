"""Support for Synology DSM binary sensors."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DISKS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import SynoApi, SynologyDSMBaseEntity, SynologyDSMDeviceEntity
from .const import (
    COORDINATOR_CENTRAL,
    DOMAIN,
    SECURITY_BINARY_SENSORS,
    STORAGE_DISK_BINARY_SENSORS,
    SYNO_API,
    UPGRADE_BINARY_SENSORS,
    SynologyDSMBinarySensorEntityDescription,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Synology NAS binary sensor."""

    data = hass.data[DOMAIN][entry.unique_id]
    api: SynoApi = data[SYNO_API]
    coordinator = data[COORDINATOR_CENTRAL]

    entities: list[
        SynoDSMSecurityBinarySensor
        | SynoDSMUpgradeBinarySensor
        | SynoDSMStorageBinarySensor
    ] = [
        SynoDSMSecurityBinarySensor(api, coordinator, description)
        for description in SECURITY_BINARY_SENSORS
    ]

    entities.extend(
        [
            SynoDSMUpgradeBinarySensor(api, coordinator, description)
            for description in UPGRADE_BINARY_SENSORS
        ]
    )

    # Handle all disks
    if api.storage.disks_ids:
        entities.extend(
            [
                SynoDSMStorageBinarySensor(api, coordinator, description, disk)
                for disk in entry.data.get(CONF_DISKS, api.storage.disks_ids)
                for description in STORAGE_DISK_BINARY_SENSORS
            ]
        )

    async_add_entities(entities)


class SynoDSMBinarySensor(SynologyDSMBaseEntity, BinarySensorEntity):
    """Mixin for binary sensor specific attributes."""

    entity_description: SynologyDSMBinarySensorEntityDescription

    def __init__(
        self,
        api: SynoApi,
        coordinator: DataUpdateCoordinator[dict[str, dict[str, Any]]],
        description: SynologyDSMBinarySensorEntityDescription,
    ) -> None:
        """Initialize the Synology DSM binary_sensor entity."""
        super().__init__(api, coordinator, description)


class SynoDSMSecurityBinarySensor(SynoDSMBinarySensor):
    """Representation a Synology Security binary sensor."""

    @property
    def is_on(self) -> bool:
        """Return the state."""
        return getattr(self._api.security, self.entity_description.key) != "safe"  # type: ignore[no-any-return]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return bool(self._api.security)

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return security checks details."""
        return self._api.security.status_by_check  # type: ignore[no-any-return]


class SynoDSMStorageBinarySensor(SynologyDSMDeviceEntity, SynoDSMBinarySensor):
    """Representation a Synology Storage binary sensor."""

    entity_description: SynologyDSMBinarySensorEntityDescription

    def __init__(
        self,
        api: SynoApi,
        coordinator: DataUpdateCoordinator[dict[str, dict[str, Any]]],
        description: SynologyDSMBinarySensorEntityDescription,
        device_id: str | None = None,
    ) -> None:
        """Initialize the Synology DSM storage binary_sensor entity."""
        super().__init__(api, coordinator, description, device_id)

    @property
    def is_on(self) -> bool:
        """Return the state."""
        return bool(
            getattr(self._api.storage, self.entity_description.key)(self._device_id)
        )


class SynoDSMUpgradeBinarySensor(SynoDSMBinarySensor):
    """Representation a Synology Upgrade binary sensor."""

    @property
    def is_on(self) -> bool:
        """Return the state."""
        return bool(getattr(self._api.upgrade, self.entity_description.key))

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return bool(self._api.upgrade)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return firmware details."""
        return {
            "installed_version": self._api.information.version_string,
            "latest_available_version": self._api.upgrade.available_version,
        }
