"""Support for SwitchBot binary sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, CONF_NAME, ENTITY_CATEGORY_DIAGNOSTIC
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import SwitchbotDataUpdateCoordinator
from .entity import SwitchbotEntity

PARALLEL_UPDATES = 1

BINARY_SENSOR_TYPES: dict[str, BinarySensorEntityDescription] = {
    "calibration": BinarySensorEntityDescription(
        key="calibration",
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Switchbot curtain based on a config entry."""
    coordinator: SwitchbotDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    if not coordinator.data[entry.unique_id].get("data"):
        return

    async_add_entities(
        [
            SwitchBotBinarySensor(
                coordinator,
                entry.unique_id,
                binary_sensor,
                entry.data[CONF_MAC],
                entry.data[CONF_NAME],
            )
            for binary_sensor in coordinator.data[entry.unique_id]["data"]
            if binary_sensor in BINARY_SENSOR_TYPES
        ]
    )


class SwitchBotBinarySensor(SwitchbotEntity, BinarySensorEntity):
    """Representation of a Switchbot binary sensor."""

    coordinator: SwitchbotDataUpdateCoordinator

    def __init__(
        self,
        coordinator: SwitchbotDataUpdateCoordinator,
        idx: str | None,
        binary_sensor: str,
        mac: str,
        switchbot_name: str,
    ) -> None:
        """Initialize the Switchbot sensor."""
        super().__init__(coordinator, idx, mac, name=switchbot_name)
        self._sensor = binary_sensor
        self._attr_unique_id = f"{idx}-{binary_sensor}"
        self._attr_name = f"{switchbot_name} {binary_sensor.title()}"
        self.entity_description = BINARY_SENSOR_TYPES[binary_sensor]

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self.data["data"][self._sensor]
