"""Binary sensor support for the Skybell HD Doorbell."""
from __future__ import annotations

from datetime import timedelta

from skybellpy.device import SkybellDevice
import voluptuous as vol

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_MOTION,
    DEVICE_CLASS_OCCUPANCY,
    PLATFORM_SCHEMA,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTITY_NAMESPACE, CONF_MONITORED_CONDITIONS
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import DOMAIN, SkybellEntity
from .const import DATA_COORDINATOR, DATA_DEVICES

SCAN_INTERVAL = timedelta(seconds=10)


BINARY_SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="button",
        name="Button",
        device_class=DEVICE_CLASS_OCCUPANCY,
    ),
    BinarySensorEntityDescription(
        key="motion",
        name="Motion",
        device_class=DEVICE_CLASS_MOTION,
    ),
)

# Deprecated in Home Assistant 2021.10
PLATFORM_SCHEMA = cv.deprecated(
    vol.All(
        PLATFORM_SCHEMA.extend(
            {
                vol.Optional(CONF_ENTITY_NAMESPACE, default=DOMAIN): cv.string,
                vol.Required(CONF_MONITORED_CONDITIONS, default=[]): vol.All(
                    cv.ensure_list, [vol.In(BINARY_SENSOR_TYPES)]
                ),
            }
        )
    )
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Skybell switch."""
    skybell = hass.data[DOMAIN][entry.entry_id]

    sensors = []
    for sensor in BINARY_SENSOR_TYPES:
        for device in skybell[DATA_DEVICES]:
            sensors.append(
                SkybellBinarySensor(
                    skybell[DATA_COORDINATOR],
                    device,
                    sensor,
                    entry.entry_id,
                )
            )

    async_add_entities(sensors, True)


class SkybellBinarySensor(SkybellEntity, BinarySensorEntity):
    """A binary sensor implementation for Skybell devices."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device: SkybellDevice,
        description: BinarySensorEntityDescription,
        server_unique_id: str,
    ) -> None:
        """Initialize a binary sensor for a Skybell device."""
        super().__init__(coordinator, device, description, server_unique_id)
        self.entity_description = description
        self._attr_name = f"{device.name} {description.name}"
        self._event: dict[str, str] = {}
        self._attr_unique_id = f"{server_unique_id}/{description.key}"

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        attrs = super().extra_state_attributes

        attrs["event_date"] = self._event.get("createdAt")

        return attrs

    @property
    def is_on(self) -> bool:
        """Return true if entity is on."""
        self._event = (
            self._device.latest(f"device:sensor:{self.entity_description.key}") or {}
        )
        return bool(self._event and self._event.get("id") != self._event.get("id"))
