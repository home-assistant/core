"""Creates button entities for the Husqvarna Automower integration."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import Any

from aioautomower.model import MowerAttributes
from aioautomower.session import AutomowerSession

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AutomowerConfigEntry
from .coordinator import AutomowerDataUpdateCoordinator
from .entity import AutomowerControlEntity, handle_sending_exception

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


async def async_reset_cutting_blade_usage_time(
    session: AutomowerSession,
    mower_id: str,
) -> None:
    """Reset cutting blade usage time."""
    await session.commands.reset_cutting_blade_usage_time(mower_id)


def reset_cutting_blade_usage_time_availability(data: MowerAttributes) -> bool:
    """Return True if blade usage time is greater than 0."""
    value = data.statistics.cutting_blade_usage_time
    return value is not None and value > 0


@dataclass(frozen=True, kw_only=True)
class AutomowerButtonEntityDescription(ButtonEntityDescription):
    """Describes Automower button entities."""

    available_fn: Callable[[MowerAttributes], bool] = lambda _: True
    exists_fn: Callable[[MowerAttributes], bool] = lambda _: True
    press_fn: Callable[[AutomowerSession, str], Awaitable[Any]]
    poll_after_sending: bool = False


MOWER_BUTTON_TYPES: tuple[AutomowerButtonEntityDescription, ...] = (
    AutomowerButtonEntityDescription(
        key="confirm_error",
        translation_key="confirm_error",
        available_fn=lambda data: data.mower.is_error_confirmable,
        exists_fn=lambda data: data.capabilities.can_confirm_error,
        press_fn=lambda session, mower_id: session.commands.error_confirm(mower_id),
    ),
    AutomowerButtonEntityDescription(
        key="sync_clock",
        translation_key="sync_clock",
        press_fn=lambda session, mower_id: session.commands.set_datetime(mower_id),
    ),
    AutomowerButtonEntityDescription(
        key="reset_cutting_blade_usage_time",
        translation_key="reset_cutting_blade_usage_time",
        available_fn=reset_cutting_blade_usage_time_availability,
        exists_fn=lambda data: data.statistics.cutting_blade_usage_time is not None,
        press_fn=async_reset_cutting_blade_usage_time,
        poll_after_sending=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AutomowerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up button platform."""
    coordinator = entry.runtime_data

    def _async_add_new_devices(mower_ids: set[str]) -> None:
        async_add_entities(
            AutomowerButtonEntity(mower_id, coordinator, description)
            for mower_id in mower_ids
            for description in MOWER_BUTTON_TYPES
            if description.exists_fn(coordinator.data[mower_id])
        )

    coordinator.new_devices_callbacks.append(_async_add_new_devices)
    _async_add_new_devices(set(coordinator.data))


class AutomowerButtonEntity(AutomowerControlEntity, ButtonEntity):
    """Defining the AutomowerButtonEntity."""

    entity_description: AutomowerButtonEntityDescription

    def __init__(
        self,
        mower_id: str,
        coordinator: AutomowerDataUpdateCoordinator,
        description: AutomowerButtonEntityDescription,
    ) -> None:
        """Set up AutomowerButtonEntity."""
        super().__init__(mower_id, coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{mower_id}_{description.key}"

    @property
    def available(self) -> bool:
        """Return the available attribute of the entity."""
        return super().available and self.entity_description.available_fn(
            self.mower_attributes
        )

    @handle_sending_exception
    async def async_press(self) -> None:
        """Send a command to the mower."""
        await self.entity_description.press_fn(self.coordinator.api, self.mower_id)
        if self.entity_description.poll_after_sending:
            await self.coordinator.async_request_refresh()
