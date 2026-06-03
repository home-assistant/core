"""Binary sensor platform for Hass.io addons."""

from collections.abc import Callable
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
class HassioAddonBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Hass.io add-on binary sensor entity description."""

    value_fn: Callable[[HassioAddonBinarySensor], bool]


@dataclass(frozen=True, kw_only=True)
class HassioMountBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Hass.io mount binary sensor entity description."""

    value_fn: Callable[[HassioMountBinarySensor], bool]


ADDON_ENTITY_DESCRIPTIONS = (
    HassioAddonBinarySensorEntityDescription(
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_registry_enabled_default=False,
        key="state",
        translation_key="state",
        value_fn=lambda entity: (
            entity.coordinator.data.addons[entity.addon_slug].addon.state
            == AddonState.STARTED
        ),
    ),
)

MOUNT_ENTITY_DESCRIPTIONS = (
    HassioMountBinarySensorEntityDescription(
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_registry_enabled_default=False,
        key="state",
        translation_key="mount",
        value_fn=lambda entity: (
            entity.coordinator.data.mounts[entity.mount_name].state == MountState.ACTIVE
        ),
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

    entity_description: HassioAddonBinarySensorEntityDescription

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.entity_description.value_fn(self)


class HassioMountBinarySensor(HassioMountEntity, BinarySensorEntity):
    """Binary sensor for Hass.io mount."""

    entity_description: HassioMountBinarySensorEntityDescription

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.entity_description.value_fn(self)
