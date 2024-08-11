"""The Aprilaire humidifier component."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, cast

from pyaprilaire.const import Attribute

from homeassistant.components.humidifier import (
    HumidifierAction,
    HumidifierDeviceClass,
    HumidifierEntity,
    HumidifierEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .coordinator import AprilaireCoordinator
from .entity import BaseAprilaireEntity

HUMIDIFIER_ACTION_MAP: dict[StateType, HumidifierAction] = {
    0: HumidifierAction.IDLE,
    1: HumidifierAction.IDLE,
    2: HumidifierAction.HUMIDIFYING,
    3: HumidifierAction.OFF,
}

DEHUMIDIFIER_ACTION_MAP: dict[StateType, HumidifierAction] = {
    0: HumidifierAction.IDLE,
    1: HumidifierAction.IDLE,
    2: HumidifierAction.DRYING,
    3: HumidifierAction.DRYING,
    4: HumidifierAction.OFF,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Aprilaire humidifier devices."""

    coordinator: AprilaireCoordinator = hass.data[DOMAIN][config_entry.unique_id]

    assert config_entry.unique_id is not None

    descriptions: list[AprilaireHumidifierDescription] = []

    if coordinator.data.get(Attribute.HUMIDIFICATION_AVAILABLE) in (0, 1, 2):
        descriptions.append(
            AprilaireHumidifierDescription(
                key="humidifier",
                translation_key="humidifier",
                device_class=HumidifierDeviceClass.HUMIDIFIER,
                action_key=Attribute.HUMIDIFICATION_STATUS,
                action_map=HUMIDIFIER_ACTION_MAP,
                current_humidity_key=Attribute.INDOOR_HUMIDITY_CONTROLLING_SENSOR_VALUE,
                target_humidity_key=Attribute.HUMIDIFICATION_SETPOINT,
                min_humidity=10,
                max_humidity=50,
                default_humidity=30,
                set_humidity_fn=coordinator.client.set_humidification_setpoint,
            )
        )

    if coordinator.data.get(Attribute.DEHUMIDIFICATION_AVAILABLE) in (0, 1):
        descriptions.append(
            AprilaireHumidifierDescription(
                key="dehumidifier",
                translation_key="dehumidifier",
                device_class=HumidifierDeviceClass.DEHUMIDIFIER,
                action_key=Attribute.DEHUMIDIFICATION_STATUS,
                action_map=DEHUMIDIFIER_ACTION_MAP,
                current_humidity_key=Attribute.INDOOR_HUMIDITY_CONTROLLING_SENSOR_VALUE,
                target_humidity_key=Attribute.DEHUMIDIFICATION_SETPOINT,
                min_humidity=40,
                max_humidity=90,
                default_humidity=60,
                set_humidity_fn=coordinator.client.set_dehumidification_setpoint,
            )
        )

    async_add_entities(
        AprilaireHumidifierEntity(coordinator, description, config_entry.unique_id)
        for description in descriptions
    )


@dataclass(frozen=True, kw_only=True)
class AprilaireHumidifierDescription(HumidifierEntityDescription):
    """Class describing Aprilaire humidifier entities."""

    action_key: str
    action_map: dict[StateType, HumidifierAction]
    current_humidity_key: str
    target_humidity_key: str
    min_humidity: int
    max_humidity: int
    default_humidity: int
    set_humidity_fn: Callable[[int], Awaitable]


class AprilaireHumidifierEntity(BaseAprilaireEntity, HumidifierEntity):
    """Base humidity entity for Aprilaire."""

    entity_description: AprilaireHumidifierDescription
    last_target_humidity: int | None = None

    def __init__(
        self,
        coordinator: AprilaireCoordinator,
        description: AprilaireHumidifierDescription,
        unique_id: str,
    ) -> None:
        """Initialize a select for an Aprilaire device."""

        self.entity_description = description

        super().__init__(coordinator, unique_id)

    @property
    def action(self) -> HumidifierAction | None:
        """Get the current action."""

        action = self.coordinator.data.get(self.entity_description.action_key)

        return self.entity_description.action_map.get(action, HumidifierAction.OFF)

    @property
    def is_on(self) -> bool:
        """Get whether the humidifier is on."""

        return self.target_humidity is not None and self.target_humidity > 0

    @property
    def current_humidity(self) -> float | None:
        """Get the current humidity."""

        return cast(
            float,
            self.coordinator.data.get(self.entity_description.current_humidity_key),
        )

    @property
    def target_humidity(self) -> float | None:
        """Get the target humidity."""

        target_humidity = cast(
            float,
            self.coordinator.data.get(self.entity_description.target_humidity_key),
        )

        if target_humidity is not None and target_humidity > 0:
            self.last_target_humidity = int(target_humidity)

        return target_humidity

    @property
    def min_humidity(self) -> float:
        """Return the minimum humidity."""

        return self.entity_description.min_humidity

    @property
    def max_humidity(self) -> float:
        """Return the maximum humidity."""

        return self.entity_description.max_humidity

    async def async_set_humidity(self, humidity: int) -> None:
        """Set the humidity."""

        await self.entity_description.set_humidity_fn(humidity)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""

        if self.last_target_humidity is None or self.last_target_humidity == 0:
            target_humidity = self.entity_description.default_humidity
        else:
            target_humidity = self.last_target_humidity

        await self.entity_description.set_humidity_fn(target_humidity)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""

        await self.entity_description.set_humidity_fn(0)
