"""Support for SwitchBot sensors."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_MAC,
    CONF_NAME,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import SwitchbotDataUpdateCoordinator
from .entity import SwitchbotEntity

PARALLEL_UPDATES = 1

SENSOR_TYPES: dict[str, SensorEntityDescription] = {
    "rssi": SensorEntityDescription(
        key="rssi",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "battery": SensorEntityDescription(
        key="battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    "lightLevel": SensorEntityDescription(
        key="lightLevel",
        native_unit_of_measurement="Level",
        device_class=SensorDeviceClass.ILLUMINANCE,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Switchbot sensor based on a config entry."""
    coordinator: SwitchbotDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    if not coordinator.data.get(entry.unique_id):
        raise PlatformNotReady

    async_add_entities(
        [
            SwitchBotSensor(
                coordinator,
                entry.unique_id,
                sensor,
                entry.data[CONF_MAC],
                entry.data[CONF_NAME],
            )
            for sensor in coordinator.data[entry.unique_id]["data"]
            if sensor in SENSOR_TYPES
        ]
    )


class SwitchBotSensor(SwitchbotEntity, SensorEntity):
    """Representation of a Switchbot sensor."""

    def __init__(
        self,
        coordinator: SwitchbotDataUpdateCoordinator,
        idx: str | None,
        sensor: str,
        mac: str,
        switchbot_name: str,
    ) -> None:
        """Initialize the Switchbot sensor."""
        super().__init__(coordinator, idx, mac, name=switchbot_name)
        self._sensor = sensor
        self._attr_unique_id = f"{idx}-{sensor}"
        self._attr_name = f"{switchbot_name} {sensor.title()}"
        self.entity_description = SENSOR_TYPES[sensor]

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        return self.data["data"][self._sensor]
