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
    entity_registry_enabled_default=False,
    entity_category=EntityCategory.DIAGNOSTIC,
)

IDENTIFY_BUTTON_DESCRIPTION = ButtonEntityDescription(
    key=IDENTIFY,
    name="Identify",
    entity_registry_enabled_default=False,
    entity_category=EntityCategory.DIAGNOSTIC,
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
        [
            LIFXRestartButton(
                coordinator=coordinator, description=RESTART_BUTTON_DESCRIPTION
            ),
            LIFXIdentifyButton(
                coordinator=coordinator, description=IDENTIFY_BUTTON_DESCRIPTION
            ),
        ]
    )


class LIFXButton(LIFXEntity, ButtonEntity):
    """Representation of a LIFX restart button."""

    _attr_has_entity_name: bool = True
    entity_description: ButtonEntityDescription

    def __init__(
        self, coordinator: LIFXUpdateCoordinator, description: ButtonEntityDescription
    ) -> None:
        """Initialise a LIFX button."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.serial_number}_{description.key}"


class LIFXRestartButton(LIFXButton):
    """Representation of a LIFX restart button."""

    async def async_press(self) -> None:
        """Restart the bulb on button press."""
        self.bulb.set_reboot()


class LIFXIdentifyButton(LIFXButton):
    """Representation of a LIFX identify button."""

    async def async_press(self) -> None:
        """Identify the bulb by flashing it when the button is pressed."""
        await self.coordinator.async_identify_bulb()
