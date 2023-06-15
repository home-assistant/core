"""Support for Roborock switch."""
import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any

from roborock.exceptions import RoborockException
from roborock.roborock_typing import RoborockCommand

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import RoborockDataUpdateCoordinator
from .device import RoborockCoordinatedEntity, RoborockEntity

_LOGGER = logging.getLogger(__name__)


@dataclass
class RoborockSwitchDescriptionMixin:
    """Define an entity description mixin for switch entities."""

    # Gets the status of the switch
    get_value: Callable[[RoborockEntity], Coroutine[Any, Any, dict]]
    # Evaluate the result of get_value to determine a bool
    evaluate_value: Callable[[dict], bool]
    # Sets the status of the switch
    set_command: Callable[[RoborockEntity, bool], Coroutine[Any, Any, dict]]
    # Check support of this feature
    check_support: Callable[[RoborockDataUpdateCoordinator], Coroutine[Any, Any, dict]]


@dataclass
class RoborockCoordinatedSwitchDescriptionMixIn:
    """Define an entity description mixin for switch entities."""

    get_value: Callable[[RoborockCoordinatedEntity], bool]
    set_command: Callable[[RoborockCoordinatedEntity, bool], Coroutine[Any, Any, dict]]
    # Check support of this feature
    check_support: Callable[[RoborockDataUpdateCoordinator], dict]


@dataclass
class RoborockSwitchDescription(
    SwitchEntityDescription, RoborockSwitchDescriptionMixin
):
    """Class to describe an Roborock switch entity."""


@dataclass
class RoborockCoordinatedSwitchDescription(
    SwitchEntityDescription, RoborockCoordinatedSwitchDescriptionMixIn
):
    """Class to describe an Roborock switch entity that needs a coordinator."""


SWITCH_DESCRIPTIONS: list[RoborockSwitchDescription] = [
    RoborockSwitchDescription(
        set_command=lambda entity, value: entity.send(
            RoborockCommand.SET_CHILD_LOCK_STATUS, {"lock_status": 1 if value else 0}
        ),
        get_value=lambda data: data.send(RoborockCommand.GET_CHILD_LOCK_STATUS),
        check_support=lambda data: data.api.send_command(
            RoborockCommand.GET_CHILD_LOCK_STATUS
        ),
        evaluate_value=lambda data: data["lock_status"] == 1,
        key="child_lock",
        translation_key="child_lock",
        icon="mdi:account-lock",
        entity_category=EntityCategory.CONFIG,
    ),
    RoborockSwitchDescription(
        set_command=lambda entity, value: entity.send(
            RoborockCommand.SET_FLOW_LED_STATUS, {"status": 1 if value else 0}
        ),
        get_value=lambda data: data.send(RoborockCommand.GET_FLOW_LED_STATUS),
        check_support=lambda data: data.api.send_command(
            RoborockCommand.GET_FLOW_LED_STATUS
        ),
        evaluate_value=lambda data: data["status"] == 1,
        key="status_indicator",
        translation_key="status_indicator",
        icon="mdi:alarm-light-outline",
        entity_category=EntityCategory.CONFIG,
    ),
]

COORDINATED_SWITCH_DESCRIPTION = [
    RoborockCoordinatedSwitchDescription(
        set_command=lambda entity, value: entity.send(
            RoborockCommand.SET_DND_TIMER,
            [
                entity.coordinator.roborock_device_info.props.dnd_timer.start_hour,
                entity.coordinator.roborock_device_info.props.dnd_timer.start_minute,
                entity.coordinator.roborock_device_info.props.dnd_timer.end_hour,
                entity.coordinator.roborock_device_info.props.dnd_timer.end_minute,
            ],
        )
        if value
        else entity.send(RoborockCommand.CLOSE_DND_TIMER),
        check_support=lambda data: data.roborock_device_info.props.dnd_timer,
        get_value=lambda data: data.coordinator.roborock_device_info.props.dnd_timer.enabled,
        key="dnd_switch",
        translation_key="dnd_switch",
        icon="mdi:bell-cancel",
        entity_category=EntityCategory.CONFIG,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Roborock switch platform."""

    coordinators: dict[str, RoborockDataUpdateCoordinator] = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    possible_entities: list[
        tuple[str, RoborockDataUpdateCoordinator, RoborockSwitchDescription]
    ] = [
        (device_id, coordinator, description)
        for device_id, coordinator in coordinators.items()
        for description in SWITCH_DESCRIPTIONS
    ]
    # We need to check if this function is supported by the device.
    results = await asyncio.gather(
        *(
            description.check_support(coordinator)
            for _, coordinator, description in possible_entities
        ),
        return_exceptions=True,
    )
    valid_entities: list[RoborockNonCoordinatedSwitchEntity] = []
    for posible_entity, result in zip(possible_entities, results):
        if isinstance(result, Exception):
            if not isinstance(result, RoborockException):
                raise result
            _LOGGER.debug("Not adding entity because of %s", result)
        else:
            valid_entities.append(
                RoborockNonCoordinatedSwitchEntity(
                    f"{posible_entity[2].key}_{slugify(posible_entity[0])}",
                    posible_entity[1],
                    posible_entity[2],
                    result,
                )
            )
    async_add_entities(
        valid_entities,
        True,
    )
    async_add_entities(
        (
            RoborockCoordinatedSwitchEntity(
                f"{description.key}_{slugify(device_id)}",
                coordinator,
                description,
            )
            for device_id, coordinator in coordinators.items()
            for description in COORDINATED_SWITCH_DESCRIPTION
            if description.check_support(coordinator) is not None
        )
    )


class RoborockNonCoordinatedSwitchEntity(RoborockEntity, SwitchEntity):
    """A class to let you turn functionality on Roborock devices on and off that does not need a coordinator."""

    entity_description: RoborockSwitchDescription

    def __init__(
        self,
        unique_id: str,
        coordinator: RoborockDataUpdateCoordinator,
        entity_description: RoborockSwitchDescription,
        initial_value: bool,
    ) -> None:
        """Create a switch entity."""
        self.entity_description = entity_description
        super().__init__(unique_id, coordinator.device_info, coordinator.api)
        self._attr_is_on = initial_value

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self.entity_description.set_command(self, False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self.entity_description.set_command(self, True)

    async def async_update(self) -> None:
        """Update switch."""
        self._attr_is_on = self.entity_description.evaluate_value(
            await self.entity_description.get_value(self)
        )


class RoborockCoordinatedSwitchEntity(RoborockCoordinatedEntity, SwitchEntity):
    """A class to let you turn functionality on Roborock devices on and off that does need a coordinator."""

    entity_description: RoborockCoordinatedSwitchDescription

    def __init__(
        self,
        unique_id: str,
        coordinator: RoborockDataUpdateCoordinator,
        entity_description: RoborockCoordinatedSwitchDescription,
    ) -> None:
        """Create a switch entity."""
        self.entity_description = entity_description
        super().__init__(unique_id, coordinator)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self.entity_description.set_command(self, False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self.entity_description.set_command(self, True)

    @property
    def is_on(self) -> bool | None:
        """Use the coordinator to determine if the switch is on."""
        return self.entity_description.get_value(self)
