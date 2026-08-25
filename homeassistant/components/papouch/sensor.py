"""Sensor platform for the Papouch integration."""

from dataclasses import dataclass
from typing import cast, override

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import UNDEFINED

from . import PapouchConfigEntry
from .coordinator import PapouchDataUpdateCoordinator
from .entity import PapouchEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PapouchSensorEntityDescription(SensorEntityDescription):
    """Description class of the Papouch sensor."""

    data_key: str
    value_key: str
    item_id: str
    translation_placeholders: dict[str, str] | None = None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PapouchConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = entry.runtime_data
    device = coordinator.device
    entities = []

    for sensor_data in device.get_supported_sensors():
        name = sensor_data["name"] if sensor_data.get("use_custom_name") else UNDEFINED

        description = PapouchSensorEntityDescription(
            key=f"{sensor_data['type']}_{sensor_data['item_id']}",
            data_key=sensor_data["type"],
            value_key=sensor_data["value_key"],
            item_id=sensor_data["item_id"],
            device_class=sensor_data.get("device_class"),
            state_class=sensor_data.get("state_class"),
            native_unit_of_measurement=sensor_data.get("unit"),
            translation_key=sensor_data.get("translation"),
            translation_placeholders=sensor_data.get("placeholder"),
            name=name,
        )
        entities.append(PapouchSensor(coordinator, description))

    async_add_entities(entities)


class PapouchSensor(PapouchEntity, SensorEntity):
    """Representation of a generic Papouch sensor."""

    entity_description: PapouchSensorEntityDescription

    def __init__(
        self,
        coordinator: PapouchDataUpdateCoordinator,
        description: PapouchSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self.entity_description = description
        mac = format_mac(coordinator.device.mac_address)
        self._attr_unique_id = f"{mac}_{description.data_key}_{description.item_id}"

        if description.translation_placeholders:
            self._attr_translation_placeholders = description.translation_placeholders

    @property
    @override
    def native_value(self) -> float | int | None:
        """Return the state of the sensor."""
        value = self.coordinator.data.get(self.entity_description.data_key, {}).get(
            self.entity_description.value_key
        )
        return cast("float | int | None", value)

    @override
    @callback
    def _handle_coordinator_update(self) -> None:
        for sensor_data in self.coordinator.device.get_supported_sensors():
            if (
                sensor_data.get("item_id") == self.entity_description.item_id
                and sensor_data.get("type") == self.entity_description.data_key
            ):
                if "unit" in sensor_data:
                    self._attr_native_unit_of_measurement = sensor_data["unit"]
                break

        super()._handle_coordinator_update()
