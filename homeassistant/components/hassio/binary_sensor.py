"""Binary sensor platform for Hass.io addons."""

from dataclasses import dataclass

from aiohasupervisor.models import AddonState
from aiohasupervisor.models.mounts import MountState

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ADDONS_COORDINATOR, MAIN_COORDINATOR
from .entity import HassioAddonEntity, HassioMountEntity


@dataclass(frozen=True, kw_only=True)
class HassioBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Hassio binary sensor entity description."""

    target: object


ADDON_ENTITY_DESCRIPTIONS = (
    HassioBinarySensorEntityDescription(
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_registry_enabled_default=False,
        key="state",
        translation_key="state",
        target=AddonState.STARTED,
    ),
)

MOUNT_ENTITY_DESCRIPTIONS = (
    HassioBinarySensorEntityDescription(
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_registry_enabled_default=False,
        key="state",
        translation_key="mount",
        target=MountState.ACTIVE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Binary sensor set up for Hass.io config entry."""
    addons_coordinator = hass.data[ADDONS_COORDINATOR]
    coordinator = hass.data[MAIN_COORDINATOR]

    async_add_entities(
        [
            *[
                HassioAddonBinarySensor(
                    addon=addon,
                    coordinator=addons_coordinator,
                    entity_description=entity_description,
                )
                for addon in addons_coordinator.data.addons.values()
                for entity_description in ADDON_ENTITY_DESCRIPTIONS
            ],
            *[
                HassioMountBinarySensor(
                    mount=mount,
                    coordinator=coordinator,
                    entity_description=entity_description,
                )
                for mount in coordinator.data.mounts.values()
                for entity_description in MOUNT_ENTITY_DESCRIPTIONS
            ],
        ]
    )


class HassioAddonBinarySensor(HassioAddonEntity, BinarySensorEntity):
    """Binary sensor for Hass.io add-ons."""

    entity_description: HassioBinarySensorEntityDescription

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return (
            getattr(
                self.coordinator.data.addons[self._addon_slug].addon,
                self.entity_description.key,
            )
            == self.entity_description.target
        )


class HassioMountBinarySensor(HassioMountEntity, BinarySensorEntity):
    """Binary sensor for Hass.io mount."""

    entity_description: HassioBinarySensorEntityDescription

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return (
            getattr(
                self.coordinator.data.mounts[self._mount.name],
                self.entity_description.key,
            )
            == self.entity_description.target
        )
