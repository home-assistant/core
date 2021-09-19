"""Support for SwitchBot sensors."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DOMAIN, MANUFACTURER, SensorType
from .coordinator import SwitchbotDataUpdateCoordinator

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


class SwitchBotSensor(CoordinatorEntity, Entity):
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
        super().__init__(coordinator)
        self._idx = idx
        self._sensor = sensor
        self._mac = mac
        self._attr_unique_id = f"{self._mac.replace(':', '')}-{sensor}"
        self._attr_name = f"{switchbot_name}.{sensor}"
        self._attr_device_class = sensor_type[0]
        self._attr_unit_of_measurement = sensor_type[1]
        self._attr_device_info: DeviceInfo = {
            "connections": {(dr.CONNECTION_NETWORK_MAC, self._mac)},
            "name": switchbot_name,
            "model": self.coordinator.data[self._idx]["modelName"],
            "manufacturer": MANUFACTURER,
        }

    @property
    def state(self) -> bool:
        """Return the state of the sensor."""
        return self.coordinator.data[self._idx]["data"][self._sensor]
