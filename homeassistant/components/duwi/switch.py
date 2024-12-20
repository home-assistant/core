"""Support for Duwi switches."""

from typing import Any

from duwi_smarthome_sdk.device_scene_models import CustomerDevice
from duwi_smarthome_sdk.manager import Manager

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DuwiConfigEntry
from .const import _LOGGER, DUWI_DISCOVERY_NEW, DPCode
from .entity import DuwiEntity

# List of Duwi switch types, each represented by a unique ID.
DUWI_SWITCH_TYPES = [
    ("1-002",),
    ("1-003",),
    ("1-005",),
    ("1-006",),
    ("107-001",),
    ("107-002",),
    ("107-003",),
]

# Map of switch type IDs to their SwitchEntityDescription objects.
SWITCHES = {
    key[0]: (
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            name=None,
            device_class=SwitchDeviceClass.SWITCH,
        ),
    )
    for key in DUWI_SWITCH_TYPES
}

# Grouped switches, allowing categorization of related entities.
GROUP_SWITCHES: dict[str, tuple[SwitchEntityDescription, ...]] = {
    "Breaker": (
        SwitchEntityDescription(
            key=DPCode.SWITCH,
            name=None,
            device_class=SwitchDeviceClass.SWITCH,
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: DuwiConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up duwi sensors dynamically through duwi discovery."""
    hass_data = entry.runtime_data

    @callback
    def async_discover_device(device_ids: list[str]) -> None:
        """Discover and add a discovered Duwi sensor."""
        entities: list[DuwiSwitchEntity] = []

        for device_id in device_ids:
            device = hass_data.manager.device_map.get(device_id)
            if not device:
                _LOGGER.warning("Device not found in device_map: %s", device_id)
                continue

            # Get the device descriptions from SWITCHES or GROUP_SWITCHES.
            descriptions = SWITCHES.get(device.device_type_no) or GROUP_SWITCHES.get(
                device.device_group_type
            )

            if descriptions:
                entities.extend(
                    DuwiSwitchEntity(device, hass_data.manager, description)
                    for description in descriptions
                )

        async_add_entities(entities)

    # Discover devices at setup time.
    async_discover_device(list(hass_data.manager.device_map.keys()))

    # Register the discovery callback.
    entry.async_on_unload(
        async_dispatcher_connect(hass, DUWI_DISCOVERY_NEW, async_discover_device)
    )


class DuwiSwitchEntity(DuwiEntity, SwitchEntity):
    """Duwi Switch Device."""

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: Manager,
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize the Duwi switch entity."""
        super().__init__(device, device_manager)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}{description.key}"

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self.device.value.get(self.entity_description.key, "off") == "on"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._send_command({self.entity_description.key: "on"})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._send_command({self.entity_description.key: "off"})
