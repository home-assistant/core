"""Sensor platform for Hass.io addons."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ADDONS_COORDINATOR
from .const import ATTR_VERSION, ATTR_VERSION_LATEST, DATA_KEY_ADDONS, DATA_KEY_OS
from .entity import HassioAddonEntity, HassioOSEntity

ENTITY_DESCRIPTIONS = (
    SensorEntityDescription(
        entity_registry_enabled_default=False,
        key=ATTR_VERSION,
        name="Version",
    ),
    SensorEntityDescription(
        entity_registry_enabled_default=False,
        key=ATTR_VERSION_LATEST,
        name="Newest Version",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Sensor set up for Hass.io config entry."""
    coordinator = hass.data[ADDONS_COORDINATOR]

    entities = []

    for entity_description in ENTITY_DESCRIPTIONS:
        for addon in coordinator.data[DATA_KEY_ADDONS].values():
            entities.append(
                HassioAddonSensor(
                    addon=addon,
                    coordinator=coordinator,
                    entity_description=entity_description,
                )
            )

        if coordinator.is_hass_os:
            entities.append(
                HassioOSSensor(
                    coordinator=coordinator,
                    entity_description=entity_description,
                )
            )

    async_add_entities(entities)


class HassioAddonSensor(HassioAddonEntity, SensorEntity):
    """Sensor to track a Hass.io add-on attribute."""

    @property
    def native_value(self) -> str:
        """Return native value of entity."""
        return self.coordinator.data[DATA_KEY_ADDONS][self._addon_slug][
            self.entity_description.key
        ]


class HassioOSSensor(HassioOSEntity, SensorEntity):
    """Sensor to track a Hass.io add-on attribute."""

    @property
    def native_value(self) -> str:
        """Return native value of entity."""
        return self.coordinator.data[DATA_KEY_OS][self.entity_description.key]
