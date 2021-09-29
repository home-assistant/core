"""Binary sensor platform for Hass.io addons."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_UPDATE,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ADDONS_COORDINATOR
from .const import ATTR_UPDATE_AVAILABLE, DATA_KEY_ADDONS, DATA_KEY_OS
from .entity import HassioAddonEntity, HassioOSEntity

ENTITY_DESCRIPTIONS = (
    BinarySensorEntityDescription(
        device_class=DEVICE_CLASS_UPDATE,
        entity_registry_enabled_default=False,
        key=ATTR_UPDATE_AVAILABLE,
        name="Update Available",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Binary sensor set up for Hass.io config entry."""
    coordinator = hass.data[ADDONS_COORDINATOR]

    entities = []

    for entity_description in ENTITY_DESCRIPTIONS:
        for addon in coordinator.data[DATA_KEY_ADDONS].values():
            entities.append(
                HassioAddonBinarySensor(
                    addon=addon,
                    coordinator=coordinator,
                    entity_description=entity_description,
                )
            )

        if coordinator.is_hass_os:
            entities.append(
                HassioOSBinarySensor(
                    coordinator=coordinator,
                    entity_description=entity_description,
                )
            )

    async_add_entities(entities)


class HassioAddonBinarySensor(HassioAddonEntity, BinarySensorEntity):
    """Binary sensor to track whether an update is available for a Hass.io add-on."""

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.coordinator.data[DATA_KEY_ADDONS][self._addon_slug][
            self.entity_description.key
        ]


class HassioOSBinarySensor(HassioOSEntity, BinarySensorEntity):
    """Binary sensor to track whether an update is available for Hass.io OS."""

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.coordinator.data[DATA_KEY_OS][self.entity_description.key]
