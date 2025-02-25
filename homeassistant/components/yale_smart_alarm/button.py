"""Support for Yale Smart Alarm button."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import YaleConfigEntry
from .const import DOMAIN, YALE_ALL_ERRORS
from .coordinator import YaleDataUpdateCoordinator
from .entity import YaleAlarmEntity

BUTTON_TYPES = (
    ButtonEntityDescription(
        key="panic",
        translation_key="panic",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YaleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the button from a config entry."""

    coordinator = entry.runtime_data

    async_add_entities(
        [YalePanicButton(coordinator, description) for description in BUTTON_TYPES]
    )


class YalePanicButton(YaleAlarmEntity, ButtonEntity):
    """A Panic button for Yale Smart Alarm."""

    entity_description: ButtonEntityDescription

    def __init__(
        self,
        coordinator: YaleDataUpdateCoordinator,
        description: ButtonEntityDescription,
    ) -> None:
        """Initialize the plug switch."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"yale_smart_alarm-{description.key}"

    async def async_press(self) -> None:
        """Press the button."""
        if TYPE_CHECKING:
            assert self.coordinator.yale, "Connection to API is missing"

        try:
            await self.hass.async_add_executor_job(
                self.coordinator.yale.trigger_panic_button
            )
        except YALE_ALL_ERRORS as error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="could_not_trigger_panic",
                translation_placeholders={
                    "entity_id": self.entity_id,
                    "error": str(error),
                },
            ) from error
