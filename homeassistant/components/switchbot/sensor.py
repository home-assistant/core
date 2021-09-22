"""Support for SwitchBot sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DATA_COORDINATOR, DOMAIN, SensorType
from .coordinator import SwitchbotDataUpdateCoordinator
from .entity import SwitchbotEntity

PARALLEL_UPDATES = 1


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
            if sensor in SensorType.__members__:
                sensor_type = getattr(SensorType, sensor).value
                sensors.append(
                    SwitchBotSensor(
                        coordinator,
                        entry.unique_id,
                        sensor,
                        sensor_type,
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
        sensor_type: str,
        mac: str,
        switchbot_name: str,
    ) -> None:
        """Initialize the Switchbot sensor."""
        super().__init__(coordinator, idx, mac, name=f"{switchbot_name}.{sensor}")
        self._sensor = sensor
        self._attr_unique_id = f"{idx}-{sensor}"
        self._attr_device_class = sensor_type[0]
        self._attr_native_unit_of_measurement = sensor_type[1]

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        return self.data["data"][self._sensor]
