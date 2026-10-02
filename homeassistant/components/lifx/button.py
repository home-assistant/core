"""Button entity for LIFX devices.."""

from typing import override

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import IDENTIFY, RESTART
from .coordinator import LIFXConfigEntry
from .entity import LIFXEntity

PARALLEL_UPDATES = 1

RESTART_BUTTON_DESCRIPTION = ButtonEntityDescription(
    key=RESTART,
    device_class=ButtonDeviceClass.RESTART,
    entity_category=EntityCategory.CONFIG,
)

IDENTIFY_BUTTON_DESCRIPTION = ButtonEntityDescription(
    key=IDENTIFY,
    device_class=ButtonDeviceClass.IDENTIFY,
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LIFXConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LIFX from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            LIFXRestartButton(coordinator, RESTART_BUTTON_DESCRIPTION),
            LIFXIdentifyButton(coordinator, IDENTIFY_BUTTON_DESCRIPTION),
        ]
    )


class LIFXRestartButton(LIFXEntity, ButtonEntity):
    """LIFX restart button."""

    @override
    async def async_press(self) -> None:
        """Restart the bulb on button press."""
        await self.coordinator.async_restart()


class LIFXIdentifyButton(LIFXEntity, ButtonEntity):
    """LIFX identify button."""

    @override
    async def async_press(self) -> None:
        """Identify the bulb by flashing it when the button is pressed."""
        await self.coordinator.async_identify_bulb()
