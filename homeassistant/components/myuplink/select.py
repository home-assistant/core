"""Select entity for myUplink."""

from aiohttp import ClientError
from myuplink import DevicePoint

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MyUplinkDataCoordinator
from .const import DOMAIN
from .entity import MyUplinkEntity
from .helpers import find_matching_platform, skip_entity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up myUplink select."""
    entities: list[SelectEntity] = []
    coordinator: MyUplinkDataCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Setup device point select entities
    for device_id, point_data in coordinator.data.points.items():
        for point_id, device_point in point_data.items():
            if skip_entity(device_point.category, device_point):
                continue
            description = None
            if find_matching_platform(device_point, description) == Platform.SELECT:
                entities.append(
                    MyUplinkSelect(
                        coordinator=coordinator,
                        device_id=device_id,
                        device_point=device_point,
                        entity_description=description,
                        unique_id_suffix=point_id,
                    )
                )

    async_add_entities(entities)


class MyUplinkSelect(MyUplinkEntity, SelectEntity):
    """Representation of a myUplink select entity."""

    def __init__(
        self,
        coordinator: MyUplinkDataCoordinator,
        device_id: str,
        device_point: DevicePoint,
        entity_description: SelectEntityDescription | None,
        unique_id_suffix: str,
    ) -> None:
        """Initialize the select."""
        super().__init__(
            coordinator=coordinator,
            device_id=device_id,
            unique_id_suffix=unique_id_suffix,
        )

        # Internal properties
        self.point_id = device_point.parameter_id
        self._attr_name = device_point.parameter_name

        self._attr_options = [x["text"].capitalize() for x in device_point.enum_values]
        self.options_map = {
            str(int(x["value"])): x["text"].capitalize()
            for x in device_point.enum_values
        }
        self.options_rev = {
            x["text"].capitalize(): str(int(x["value"]))
            for x in device_point.enum_values
        }

    @property
    def current_option(self) -> str | None:
        """Retrieve currently selected option."""
        device_point = self.coordinator.data.points[self.device_id][self.point_id]
        value = device_point.value_t
        if isinstance(device_point.value_t, float):
            value = int(device_point.value_t)
        return self.options_map.get(str(value))

    async def async_select_option(self, option: str) -> None:
        """Set the current option."""
        try:
            await self.coordinator.api.async_set_device_points(
                self.device_id, data={self.point_id: str(self.options_rev[option])}
            )
        except ClientError as err:
            raise HomeAssistantError(
                f"Failed to set new option {self.options_rev[option]} for {self.point_id}/{self.entity_id}"
            ) from err

        await self.coordinator.async_request_refresh()
