"""Button entity for LIFX devices.."""
from __future__ import annotations

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, RESTART
from .coordinator import LIFXUpdateCoordinator

RESTART_BUTTON_DESCRIPTION = ButtonEntityDescription(
    key=RESTART,
    name="Restart",
    device_class=ButtonDeviceClass.RESTART,
    entity_registry_enabled_default=False,
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
            )
        ]
    )


class LIFXRestartButton(CoordinatorEntity[LIFXUpdateCoordinator], ButtonEntity):
    """Representation of a LIFX restart button."""

    _attr_has_entity_name: bool = True
    entity_description: ButtonEntityDescription

    def __init__(
        self, coordinator: LIFXUpdateCoordinator, description: ButtonEntityDescription
    ) -> None:
        """Initialise the restart button."""
        super().__init__(coordinator=coordinator)
        self.entity_description: ButtonEntityDescription = description
        self.coordinator: LIFXUpdateCoordinator = coordinator
        self._attr_name = self.entity_description.name
        self._attr_unique_id = (
            f"{self.coordinator.serial_number}_{self.entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            connections={(dr.CONNECTION_NETWORK_MAC, self.coordinator.mac_address)},
            manufacturer="LIFX",
            name=self.coordinator.label,
        )

    async def async_press(self) -> None:
        """Restart the bulb on button press."""
        await self.coordinator.async_set_reboot()
