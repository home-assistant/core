"""Support for SwitchBot sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_MAC,
    CONF_NAME,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import SwitchbotDataUpdateCoordinator
from .entity import SwitchbotEntity

PARALLEL_UPDATES = 1

SENSOR_TYPES: dict[str, SensorEntityDescription] = {
    "rssi": SensorEntityDescription(
        key="rssi",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        device_class=DEVICE_CLASS_SIGNAL_STRENGTH,
        entity_registry_enabled_default=False,
    ),
    "battery": SensorEntityDescription(
        key="battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=DEVICE_CLASS_BATTERY,
    ),
    "lightLevel": SensorEntityDescription(
        key="lightLevel",
        native_unit_of_measurement="Level",
        device_class=DEVICE_CLASS_ILLUMINANCE,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Switchbot sensor based on a config entry."""
    coordinator: SwitchbotDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    sensors = []

    if coordinator.data[entry.unique_id].get("data"):
        for sensor in coordinator.data[entry.unique_id].get("data"):
            if sensor in SENSOR_TYPES:
                sensors.append(
                    SwitchBotSensor(
                        coordinator,
                        entry.unique_id,
                        sensor,
                        entry.data[CONF_MAC],
                        entry.data[CONF_NAME],
                    )
                )

    async_add_entities(sensors)


class SwitchBotSensor(SwitchbotEntity, SensorEntity):
    """Representation of a Switchbot sensor."""

    coordinator: SwitchbotDataUpdateCoordinator

    def __init__(
        self,
        coordinator: SwitchbotDataUpdateCoordinator,
        idx: str | None,
        sensor: str,
        mac: str,
        switchbot_name: str,
    ) -> None:
        """Initialize the Switchbot sensor."""
        super().__init__(coordinator, idx, mac, name=f"{switchbot_name}.{sensor}")
        self._sensor = sensor
        self._attr_unique_id = f"{idx}-{sensor}"
        self.entity_description = SENSOR_TYPES[sensor]

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        return self.data["data"][self._sensor]
