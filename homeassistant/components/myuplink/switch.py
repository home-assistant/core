"""Switch entity for myUplink."""

from typing import Any

from myuplink import DevicePoint

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MyUplinkDataCoordinator
from .const import DOMAIN
from .entity import MyUplinkEntity
from .helpers import find_matching_platform

CATEGORY_BASED_DESCRIPTIONS: dict[str, dict[str, SwitchEntityDescription]] = {
    "NIBEF": {
        "50004": SwitchEntityDescription(
            key="temporary_lux",
            icon="mdi:water-alert-outline",
        ),
    },
}


def get_description(device_point: DevicePoint) -> SwitchEntityDescription | None:
    """Get description for a device point.

    Priorities:
    1. Category specific prefix e.g "NIBEF"
    2. Default to None
    """
    prefix, _, _ = device_point.category.partition(" ")
    description = CATEGORY_BASED_DESCRIPTIONS.get(prefix, {}).get(
        device_point.parameter_id
    )

    return description


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up myUplink switch."""
    entities: list[SwitchEntity] = []
    coordinator: MyUplinkDataCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Setup device point sensors
    for device_id, point_data in coordinator.data.points.items():
        for point_id, device_point in point_data.items():
            if find_matching_platform(device_point) == Platform.SWITCH:
                description = get_description(device_point)

                entities.append(
                    MyUplinkDevicePointSwitch(
                        coordinator=coordinator,
                        device_id=device_id,
                        device_point=device_point,
                        entity_description=description,
                        unique_id_suffix=point_id,
                    )
                )

    async_add_entities(entities)


class MyUplinkDevicePointSwitch(MyUplinkEntity, SwitchEntity):
    """Representation of a myUplink device point sensor."""

    def __init__(
        self,
        coordinator: MyUplinkDataCoordinator,
        device_id: str,
        device_point: DevicePoint,
        entity_description: SwitchEntityDescription | None,
        unique_id_suffix: str,
    ) -> None:
        """Initialize the switch."""
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
        """Switch state value."""
        device_point = self.coordinator.data.points[self.device_id][self.point_id]
        return int(device_point.value) != 0

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on switch."""
        await self._async_turn_switch(1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off switch."""
        await self._async_turn_switch(0)

    async def _async_turn_switch(self, mode: int) -> None:
        """Set switch mode."""
        await self.coordinator.api.async_set_device_points(
            self.device_id, data={self.point_id: mode}
        )
        await self.coordinator.async_request_refresh()
