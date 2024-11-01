"""Number entity for myUplink."""

from aiohttp import ClientError
from myuplink import DevicePoint

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MyUplinkConfigEntry, MyUplinkDataCoordinator
from .entity import MyUplinkEntity
from .helpers import find_matching_platform, skip_entity

DEVICE_POINT_UNIT_DESCRIPTIONS: dict[str, NumberEntityDescription] = {
    "DM": NumberEntityDescription(
        key="degree_minutes",
        translation_key="degree_minutes",
        native_unit_of_measurement="DM",
    ),
}

CATEGORY_BASED_DESCRIPTIONS: dict[str, dict[str, NumberEntityDescription]] = {
    "F730": {
        "40940": NumberEntityDescription(
            key="degree_minutes",
            translation_key="degree_minutes",
            native_unit_of_measurement="DM",
        ),
    },
    "NIBEF": {
        "40940": NumberEntityDescription(
            key="degree_minutes",
            translation_key="degree_minutes",
            native_unit_of_measurement="DM",
        ),
    },
}


def get_description(device_point: DevicePoint) -> NumberEntityDescription | None:
    """Get description for a device point.

    Priorities:
    1. Category specific prefix e.g "NIBEF"
    2. Global parameter_unit e.g. "DM"
    3. Default to None
    """
    prefix, _, _ = device_point.category.partition(" ")
    description = CATEGORY_BASED_DESCRIPTIONS.get(prefix, {}).get(
        device_point.parameter_id
    )

    if description is None:
        description = DEVICE_POINT_UNIT_DESCRIPTIONS.get(device_point.parameter_unit)

    return description


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MyUplinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up myUplink number."""
    entities: list[NumberEntity] = []
    coordinator = config_entry.runtime_data

    # Setup device point number entities
    for device_id, point_data in coordinator.data.points.items():
        for point_id, device_point in point_data.items():
            if skip_entity(device_point.category, device_point):
                continue
            description = get_description(device_point)
            if find_matching_platform(device_point, description) == Platform.NUMBER:
                entities.append(
                    MyUplinkNumber(
                        coordinator=coordinator,
                        device_id=device_id,
                        device_point=device_point,
                        entity_description=description,
                        unique_id_suffix=point_id,
                    )
                )

    async_add_entities(entities)


class MyUplinkNumber(MyUplinkEntity, NumberEntity):
    """Representation of a myUplink number entity."""

    def __init__(
        self,
        coordinator: MyUplinkDataCoordinator,
        device_id: str,
        device_point: DevicePoint,
        entity_description: NumberEntityDescription | None,
        unique_id_suffix: str,
    ) -> None:
        """Initialize the number."""
        super().__init__(
            coordinator=coordinator,
            device_id=device_id,
            unique_id_suffix=unique_id_suffix,
        )

        # Internal properties
        self.point_id = device_point.parameter_id
        self._attr_name = device_point.parameter_name
        self._attr_native_min_value = (
            device_point.raw["minValue"] if device_point.raw["minValue"] else -30000
        ) * float(device_point.raw.get("scaleValue", 1))
        self._attr_native_max_value = (
            device_point.raw["maxValue"] if device_point.raw["maxValue"] else 30000
        ) * float(device_point.raw.get("scaleValue", 1))
        self._attr_step_value = device_point.raw.get("stepValue", 20)
        if entity_description is not None:
            self.entity_description = entity_description

    @property
    def native_value(self) -> float:
        """Number state value."""
        device_point = self.coordinator.data.points[self.device_id][self.point_id]
        return float(device_point.value)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        try:
            await self.coordinator.api.async_set_device_points(
                self.device_id, data={self.point_id: str(value)}
            )
        except ClientError as err:
            raise HomeAssistantError(
                f"Failed to set new value {value} for {self.point_id}/{self.entity_id}"
            ) from err

        await self.coordinator.async_request_refresh()
