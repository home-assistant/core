"""Switch entity for myUplink."""

from typing import Any

import aiohttp
from myuplink import DevicePoint

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MyUplinkConfigEntry, MyUplinkDataCoordinator
from .const import DOMAIN, F_SERIES
from .entity import MyUplinkEntity
from .helpers import find_matching_platform, skip_entity, transform_model_series

CATEGORY_BASED_DESCRIPTIONS: dict[str, dict[str, SwitchEntityDescription]] = {
    F_SERIES: {
        "50004": SwitchEntityDescription(
            key="temporary_lux",
            translation_key="temporary_lux",
        ),
        "50005": SwitchEntityDescription(
            key="boost_ventilation",
            translation_key="boost_ventilation",
        ),
    },
    "NIBEF": {
        "50004": SwitchEntityDescription(
            key="temporary_lux",
            translation_key="temporary_lux",
        ),
        "50005": SwitchEntityDescription(
            key="boost_ventilation",
            translation_key="boost_ventilation",
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
    prefix = transform_model_series(prefix)
    return CATEGORY_BASED_DESCRIPTIONS.get(prefix, {}).get(device_point.parameter_id)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MyUplinkConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up myUplink switch."""
    entities: list[SwitchEntity] = []
    coordinator = config_entry.runtime_data

    # Setup device point switches
    for device_id, point_data in coordinator.data.points.items():
        for point_id, device_point in point_data.items():
            if skip_entity(device_point.category, device_point):
                continue
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
    """Representation of a myUplink device point switch."""

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
        try:
            await self.coordinator.api.async_set_device_points(
                self.device_id, data={self.point_id: mode}
            )
        except aiohttp.ClientError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_switch_error",
                translation_placeholders={
                    "entity": self.entity_id,
                },
            ) from err

        await self.coordinator.async_request_refresh()
