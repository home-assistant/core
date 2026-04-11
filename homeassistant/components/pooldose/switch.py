"""Switches for the Seko PoolDose integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PooldoseConfigEntry
from .entity import PooldoseEntity

if TYPE_CHECKING:
    from .coordinator import PooldoseCoordinator

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1


SWITCH_DESCRIPTIONS: tuple[SwitchEntityDescription, ...] = (
    SwitchEntityDescription(
        key="pause_dosing",
        translation_key="pause_dosing",
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="pump_monitoring",
        translation_key="pump_monitoring",
        entity_category=EntityCategory.CONFIG,
    ),
    SwitchEntityDescription(
        key="frequency_input",
        translation_key="frequency_input",
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PooldoseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PoolDose switch entities from a config entry."""
    if TYPE_CHECKING:
        assert config_entry.unique_id is not None

    coordinator = config_entry.runtime_data
    switch_data = coordinator.data["switch"]
    serial_number = config_entry.unique_id

    async_add_entities(
        PooldoseSwitch(coordinator, serial_number, coordinator.device_info, description)
        for description in SWITCH_DESCRIPTIONS
        if description.key in switch_data
    )


class PooldoseSwitch(PooldoseEntity, SwitchEntity):
    """Switch entity for the Seko PoolDose Python API."""

    def __init__(
        self,
        coordinator: PooldoseCoordinator,
        serial_number: str,
        device_info: Any,
        description: SwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, serial_number, device_info, description, "switch")
        self._async_update_attrs()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_attrs()
        super()._handle_coordinator_update()

    def _async_update_attrs(self) -> None:
        """Update switch attributes."""
        data = cast(dict, self.get_data())
        self._attr_is_on = cast(bool, data["value"])

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._async_perform_write(
            self.coordinator.client.set_switch, self.entity_description.key, True
        )

        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_perform_write(
            self.coordinator.client.set_switch, self.entity_description.key, False
        )

        self._attr_is_on = False
        self.async_write_ha_state()
