"""Binary sensors for myUplink."""

from myuplink import DevicePoint

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MyUplinkDataCoordinator
from .const import DOMAIN
from .entity import MyUplinkEntity
from .helpers import find_matching_platform

CATEGORY_BASED_DESCRIPTIONS: dict[str, dict[str, BinarySensorEntityDescription]] = {
    "NIBEF": {
        "43161": BinarySensorEntityDescription(
            key="elect_add",
            translation_key="elect_add",
        ),
    },
}


def get_description(device_point: DevicePoint) -> BinarySensorEntityDescription | None:
    """Get description for a device point.

    Priorities:
    1. Category specific prefix e.g "NIBEF"
    2. Default to None
    """
    prefix, _, _ = device_point.category.partition(" ")
    return CATEGORY_BASED_DESCRIPTIONS.get(prefix, {}).get(device_point.parameter_id)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up myUplink binary_sensor."""
    entities: list[BinarySensorEntity] = []
    coordinator: MyUplinkDataCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Setup device point sensors
    for device_id, point_data in coordinator.data.points.items():
        for point_id, device_point in point_data.items():
            if find_matching_platform(device_point) == Platform.BINARY_SENSOR:
                description = get_description(device_point)

                entities.append(
                    MyUplinkDevicePointBinarySensor(
                        coordinator=coordinator,
                        device_id=device_id,
                        device_point=device_point,
                        entity_description=description,
                        unique_id_suffix=point_id,
                    )
                )
    async_add_entities(entities)


class MyUplinkDevicePointBinarySensor(MyUplinkEntity, BinarySensorEntity):
    """Representation of a myUplink device point binary sensor."""

    def __init__(
        self,
        coordinator: MyUplinkDataCoordinator,
        device_id: str,
        device_point: DevicePoint,
        entity_description: BinarySensorEntityDescription | None,
        unique_id_suffix: str,
    ) -> None:
        """Initialize the binary_sensor."""
        super().__init__(
            coordinator=coordinator,
            device_id=device_id,
            unique_id_suffix=unique_id_suffix,
        )

        # Internal properties
        self.point_id = device_point.parameter_id
        self._attr_name = device_point.parameter_name

        if entity_description is not None:
            self.entity_description = entity_description

    @property
    def is_on(self) -> bool:
        """Binary sensor state value."""
        device_point = self.coordinator.data.points[self.device_id][self.point_id]
        return int(device_point.value) != 0
