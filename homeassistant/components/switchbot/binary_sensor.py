"""Support for SwitchBot binary sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DOMAIN, MANUFACTURER, BinarySensorType
from .coordinator import SwitchbotDataUpdateCoordinator

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Switchbot curtain based on a config entry."""
    coordinator: SwitchbotDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]

    binary_sensors = []

    if coordinator.data[entry.unique_id].get("data"):
        for sensor in coordinator.data[entry.unique_id].get("data"):
            if sensor in BinarySensorType.__members__:
                device_class = getattr(BinarySensorType, sensor).value
                binary_sensors.append(
                    SwitchBotBinarySensor(
                        coordinator,
                        entry.unique_id,
                        sensor,
                        device_class,
                        entry.data[CONF_MAC],
                        entry.data[CONF_NAME],
                    )
                )

    async_add_entities(binary_sensors)


class SwitchBotBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a Switchbot binary sensor."""

    coordinator: SwitchbotDataUpdateCoordinator

    def __init__(
        self,
        coordinator: SwitchbotDataUpdateCoordinator,
        idx: str | None,
        sensor: str,
        device_class: str,
        mac: str,
        switchbot_name: str,
    ) -> None:
        """Initialize the Switchbot sensor."""
        super().__init__(coordinator)
        self._idx = idx
        self._sensor = sensor
        self._mac = mac
        self._attr_device_class = device_class
        self._model = self.coordinator.data[self._idx]["modelName"]
        self._attr_unique_id = f"{idx}-{sensor}"
        self._attr_name = f"{switchbot_name}.{sensor}"
        self._attr_device_info: DeviceInfo = {
            "connections": {(dr.CONNECTION_NETWORK_MAC, self._mac)},
            "name": switchbot_name,
            "model": self._model,
            "manufacturer": MANUFACTURER,
        }

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self.coordinator.data[self._idx]["data"][self._sensor]
