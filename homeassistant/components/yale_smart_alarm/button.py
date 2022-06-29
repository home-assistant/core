"""Support for Yale Smart Alarm button."""
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import COORDINATOR, DOMAIN
from .coordinator import YaleDataUpdateCoordinator
from .entity import YaleAlarmEntity

BUTTON_TYPES = (
    ButtonEntityDescription(key="panic", name="Panic Button", icon="mdi:alarm-light"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the button from a config entry."""

    coordinator: YaleDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        COORDINATOR
    ]

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
        self._attr_name = f"{coordinator.entry.data[CONF_NAME]} {description.name}"
        self._attr_unique_id = f"yale_smart_alarm-{description.key}"

    async def async_press(self) -> None:
        """Press the button."""
        if TYPE_CHECKING:
            assert self.coordinator.yale, "Connection to API is missing"

        await self.hass.async_add_executor_job(
            self.coordinator.yale.trigger_panic_button
        )
