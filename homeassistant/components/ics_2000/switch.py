"""Platform for ICS-2000 integration."""

from __future__ import annotations

import logging
from typing import Any

from ics_2000.entities import switch_device

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HubConfigEntry
from .const import DOMAIN
from .coordinator import ICS200Coordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HubConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Setup the switches."""

    async_add_entities(
        [
            Switch(entry.runtime_data, entity, entry.runtime_data.hub.local_address)
            for entity in entry.runtime_data.hub.devices
            if type(entity) is switch_device.SwitchDevice
        ]
    )


class Switch(CoordinatorEntity[ICS200Coordinator], SwitchEntity):
    """Representation of an switches light."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        coordinator: ICS200Coordinator,
        switch: switch_device.SwitchDevice,
        local_address: str | None,
    ) -> None:
        """Initialize an switch."""
        super().__init__(coordinator, context=str(switch.entity_id))
        self._switch = switch
        self._state = False
        self._local_address = local_address
        self._attr_unique_id = str(switch.entity_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, switch.device_data.id)},
            name=str(switch.name),
            model=switch.device_config.model_name,
            model_id=str(switch.device_data.device),
            sw_version=str(
                switch.device_data.data.get("module", {}).get("version", "")
            ),
        )

    @property
    def icon(self) -> str | None:
        """Icon of the entity."""
        return "mdi:flash"

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        return self._state

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the switch to turn on."""
        await self.hass.async_add_executor_job(
            self._switch.turn_on, self._local_address is not None
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the switch to turn off."""
        await self.hass.async_add_executor_job(
            self._switch.turn_off, self._local_address is not None
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        status = self.coordinator.hub.device_statuses.get(self._switch.entity_id, [])
        if self._switch.device_config.on_off_function is not None:
            self._state = status[self._switch.device_config.on_off_function] == 1
        self.async_write_ha_state()
