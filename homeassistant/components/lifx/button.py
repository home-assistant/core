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
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, IDENTIFY, RESTART
from .coordinator import LIFXUpdateCoordinator

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


class LIFXButton(CoordinatorEntity[LIFXUpdateCoordinator], ButtonEntity):
    """Representation of a LIFX restart button."""

    _attr_has_entity_name: bool = True
    entity_description: ButtonEntityDescription

    def __init__(
        self, coordinator: LIFXUpdateCoordinator, description: ButtonEntityDescription
    ) -> None:
        """Initialise a LIFX button."""
        super().__init__(coordinator=coordinator)
        self.entity_description: ButtonEntityDescription = description
        self.coordinator: LIFXUpdateCoordinator = coordinator
        self._attr_name = self.entity_description.name
        self._attr_unique_id = (
            f"{self.coordinator.serial_number}_{self.entity_description.key}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.serial_number)},
            connections={(dr.CONNECTION_NETWORK_MAC, self.coordinator.mac_address)},
            manufacturer="LIFX",
            name=self.coordinator.label,
        )


class LIFXRestartButton(LIFXButton):
    """Representation of a LIFX restart button."""

    async def async_press(self) -> None:
        """Restart the bulb on button press."""
        self.coordinator.device.set_reboot()


class LIFXIdentifyButton(LIFXButton):
    """Representation of a LIFX identify button."""

    async def async_press(self) -> None:
        """Identify the bulb by flashing it when the button is pressed."""
        identify = {
            "transient": True,
            "color": [0, 0, 1, 3500],
            "skew_ratio": 0,
            "period": 1000,
            "cycles": 3,
            "waveform": 1,
            "set_hue": True,
            "set_saturation": True,
            "set_brightness": True,
            "set_kelvin": True,
        }
        await self.coordinator.async_set_waveform_optional(value=identify)
