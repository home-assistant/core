"""Switch platform for Wireless Sensor Tags."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WirelessTagDataUpdateCoordinator

PARALLEL_UPDATES = 0

SWITCH_DESCRIPTIONS: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key="temperature",
        translation_key="arm_temperature",
    ),
    SwitchEntityDescription(
        key="humidity",
        translation_key="arm_humidity",
    ),
    SwitchEntityDescription(
        key="motion",
        translation_key="arm_motion",
    ),
    SwitchEntityDescription(
        key="light",
        translation_key="arm_light",
    ),
    SwitchEntityDescription(
        key="moisture",
        translation_key="arm_moisture",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Wireless Tag switch platform."""
    coordinator: WirelessTagDataUpdateCoordinator = config_entry.runtime_data

    def _async_add_entities_for_tags(tag_ids: set[str]) -> None:
        """Add switch entities for the given tag IDs."""
        entities = [
            WirelessTagSwitch(coordinator, tag_id, description)
            for tag_id in tag_ids
            if tag_id in coordinator.data
            for description in SWITCH_DESCRIPTIONS
            # Only create switch if the tag supports this sensor type
            if coordinator.data[tag_id].get(description.key) is not None
        ]
        async_add_entities(entities)

    # Register callback for dynamic device addition
    coordinator.new_devices_callbacks.append(_async_add_entities_for_tags)

    # Create switch entities for arming/disarming sensor monitoring
    if coordinator.data:
        _async_add_entities_for_tags(set(coordinator.data.keys()))


class WirelessTagSwitch(
    CoordinatorEntity[WirelessTagDataUpdateCoordinator], SwitchEntity
):
    """Implementation of a Wireless Tag switch for arming/disarming sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: WirelessTagDataUpdateCoordinator,
        tag_id: str,
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self.entity_description = description
        self._tag_id = tag_id

        # Set unique ID
        tag_data = coordinator.data[tag_id]
        self._attr_unique_id = f"{tag_data['uuid']}_arm_{description.key}"

        # Set device info (static)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, tag_data["uuid"])},
            name=tag_data["name"],
            manufacturer="Wireless Sensor Tag",
            model="Wireless Sensor Tag",
            sw_version=tag_data.get("version"),
            serial_number=tag_data["uuid"],
        )

        # Initialize state
        self._update_from_coordinator()

    def _update_from_coordinator(self) -> None:
        """Update entity state from coordinator data."""
        if self._tag_id not in self.coordinator.data:
            self._attr_available = False
            self._attr_is_on = False
            return

        tag_data = self.coordinator.data[self._tag_id]
        self._attr_available = tag_data["is_alive"]
        # Switch state is whether the sensor monitoring is armed
        armed_key = f"{self.entity_description.key}_armed"
        self._attr_is_on = tag_data.get(armed_key, False)

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_from_coordinator()
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on (arm the sensor)."""
        await self.coordinator.async_arm_tag(self._tag_id, self.entity_description.key)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off (disarm the sensor)."""
        await self.coordinator.async_disarm_tag(
            self._tag_id, self.entity_description.key
        )
