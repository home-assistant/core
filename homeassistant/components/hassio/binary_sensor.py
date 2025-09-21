"""Binary sensor platform for Hass.io addons."""

from __future__ import annotations

from dataclasses import dataclass

from aiohasupervisor.models.mounts import MountState

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    ADDONS_COORDINATOR,
    ATTR_STARTED,
    ATTR_STATE,
    DATA_KEY_ADDONS,
    DATA_KEY_MOUNTS,
)
from .entity import HassioAddonEntity, HassioMountEntity


@dataclass(frozen=True)
class HassioBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Hassio binary sensor entity description."""

    target: str | None = None


ADDON_ENTITY_DESCRIPTIONS = (
    HassioBinarySensorEntityDescription(
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_registry_enabled_default=False,
        key=ATTR_STATE,
        translation_key="state",
        target=ATTR_STARTED,
    ),
)

MOUNT_ENTITY_DESCRIPTIONS = (
    HassioBinarySensorEntityDescription(
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_registry_enabled_default=False,
        key=ATTR_STATE,
        translation_key="mount",
        target=MountState.ACTIVE.value,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Binary sensor set up for Hass.io config entry."""
    coordinator = hass.data[ADDONS_COORDINATOR]

    async_add_entities(
        [
            HassioAddonBinarySensor(
                addon=addon,
                coordinator=coordinator,
                entity_description=entity_description,
            )
            for addon in coordinator.data[DATA_KEY_ADDONS].values()
            for entity_description in ADDON_ENTITY_DESCRIPTIONS
        ]
        + [
            HassioMountBinarySensor(
                mount=mount,
                coordinator=coordinator,
                entity_description=entity_description,
            )
            for mount in coordinator.data[DATA_KEY_MOUNTS].values()
            for entity_description in MOUNT_ENTITY_DESCRIPTIONS
        ]
    )


class HassioAddonBinarySensor(HassioAddonEntity, BinarySensorEntity):
    """Binary sensor for Hass.io add-ons."""

    entity_description: HassioBinarySensorEntityDescription

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        value = self.coordinator.data[DATA_KEY_ADDONS][self._addon_slug][
            self.entity_description.key
        ]
        if self.entity_description.target is None:
            return value
        return value == self.entity_description.target


class HassioMountBinarySensor(HassioMountEntity, BinarySensorEntity):
    """Binary sensor for Hass.io mount."""

    entity_description: HassioBinarySensorEntityDescription

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        value = getattr(
            self.coordinator.data[DATA_KEY_MOUNTS][self._mount.name],
            self.entity_description.key,
        )
        if self.entity_description.target is None:
            return value
        return value == self.entity_description.target
