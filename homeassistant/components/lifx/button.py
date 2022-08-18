"""Button entity for LIFX devices.."""
from __future__ import annotations

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, IDENTIFY, RESTART
from .coordinator import LIFXUpdateCoordinator
from .entity import LIFXEntity

RESTART_BUTTON_DESCRIPTION = ButtonEntityDescription(
    key=RESTART,
    name="Restart",
    device_class=ButtonDeviceClass.RESTART,
    entity_category=EntityCategory.CONFIG,
)

IDENTIFY_BUTTON_DESCRIPTION = ButtonEntityDescription(
    key=IDENTIFY,
    name="Identify",
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LIFX from a config entry."""
    domain_data = hass.data[DOMAIN]
    coordinator: LIFXUpdateCoordinator = domain_data[entry.entry_id]
    async_add_entities(
        cls(coordinator) for cls in (LIFXRestartButton, LIFXIdentifyButton)
    )


class LIFXButton(LIFXEntity, ButtonEntity):
    """Base LIFX button."""

    _attr_has_entity_name: bool = True

    def __init__(self, coordinator: LIFXUpdateCoordinator) -> None:
        """Initialise a LIFX button."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{coordinator.serial_number}_{self.entity_description.key}"
        )


class LIFXRestartButton(LIFXButton):
    """LIFX restart button."""

    entity_description = RESTART_BUTTON_DESCRIPTION

    async def async_press(self) -> None:
        """Restart the bulb on button press."""
        self.bulb.set_reboot()


class LIFXIdentifyButton(LIFXButton):
    """LIFX identify button."""

    entity_description = IDENTIFY_BUTTON_DESCRIPTION

    async def async_press(self) -> None:
        """Identify the bulb by flashing it when the button is pressed."""
        await self.coordinator.async_identify_bulb()
