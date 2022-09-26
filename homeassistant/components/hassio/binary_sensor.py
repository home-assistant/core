"""Binary sensor platform for Hass.io addons."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ADDONS_COORDINATOR
from .const import ATTR_STARTED, ATTR_STATE, DATA_KEY_ADDONS
from .entity import HassioAddonEntity


@dataclass
class HassioBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Hassio binary sensor entity description."""

    target: str | None = None


ADDON_ENTITY_DESCRIPTIONS = (
    HassioBinarySensorEntityDescription(
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_registry_enabled_default=False,
        key=ATTR_STATE,
        name="Running",
        target=ATTR_STARTED,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Binary sensor set up for Hass.io config entry."""
    coordinator = hass.data[ADDONS_COORDINATOR]

    async_add_entities(
        HassioAddonBinarySensor(
            addon=addon,
            coordinator=coordinator,
            entity_description=entity_description,
        )
        for addon in coordinator.data[DATA_KEY_ADDONS].values()
        for entity_description in ADDON_ENTITY_DESCRIPTIONS
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
