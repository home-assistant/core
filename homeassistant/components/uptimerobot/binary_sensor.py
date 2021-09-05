"""A platform that to monitor Uptime Robot monitors."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    PLATFORM_SCHEMA,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .entity import UptimeRobotEntity

PLATFORM_SCHEMA = cv.deprecated(
    vol.All(PLATFORM_SCHEMA.extend({vol.Required(CONF_API_KEY): cv.string}))
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Uptime Robot binary_sensor platform."""
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Uptime Robot binary_sensors."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            UptimeRobotBinarySensor(
                coordinator,
                BinarySensorEntityDescription(
                    key=str(monitor.id),
                    name=monitor.friendly_name,
                    device_class=DEVICE_CLASS_CONNECTIVITY,
                ),
                monitor=monitor,
            )
            for monitor in coordinator.data
        ],
    )


class UptimeRobotBinarySensor(UptimeRobotEntity, BinarySensorEntity):
    """Representation of a Uptime Robot binary sensor."""

    @property
    def is_on(self) -> bool:
        """Return True if the entity is on."""
        return self.monitor_available
