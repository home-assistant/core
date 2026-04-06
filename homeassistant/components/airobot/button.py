"""Button platform for Airobot integration."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from pyairobotrest.exceptions import (
    AirobotConnectionError,
    AirobotError,
    AirobotTimeoutError,
)

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import AirobotConfigEntry, AirobotDataUpdateCoordinator
from .entity import AirobotEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AirobotButtonEntityDescription(ButtonEntityDescription):
    """Describes Airobot button entity."""

    press_fn: Callable[[AirobotDataUpdateCoordinator], Coroutine[Any, Any, None]]


BUTTON_TYPES: tuple[AirobotButtonEntityDescription, ...] = (
    AirobotButtonEntityDescription(
        key="restart",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda coordinator: coordinator.client.reboot_thermostat(),
    ),
    AirobotButtonEntityDescription(
        key="recalibrate_co2",
        translation_key="recalibrate_co2",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        press_fn=lambda coordinator: coordinator.client.recalibrate_co2_sensor(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirobotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Airobot button entities."""
    coordinator = entry.runtime_data

    async_add_entities(
        AirobotButton(coordinator, description) for description in BUTTON_TYPES
    )


class AirobotButton(AirobotEntity, ButtonEntity):
    """Representation of an Airobot button."""

    entity_description: AirobotButtonEntityDescription

    def __init__(
        self,
        coordinator: AirobotDataUpdateCoordinator,
        description: AirobotButtonEntityDescription,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.status.device_id}_{description.key}"

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            await self.entity_description.press_fn(self.coordinator)
        except AirobotConnectionError, AirobotTimeoutError:
            # Connection errors during reboot are expected as device restarts
            pass
        except AirobotError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="button_press_failed",
                translation_placeholders={"button": self.entity_description.key},
            ) from err
