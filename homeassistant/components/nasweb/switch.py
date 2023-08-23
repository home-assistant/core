"""Platform for NASweb output."""
from __future__ import annotations

import logging
from typing import Any

from webio_api import Output as NASwebOutput
from webio_api.const import KEY_OUTPUTS

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, OUTPUT_TRANSLATION_KEY
from .coordinator import NASwebCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up switch platform."""
    coordinator = hass.data[DOMAIN][config.entry_id]
    nasweb_outputs = coordinator.data[KEY_OUTPUTS]
    entities: list[Output] = []
    for out in nasweb_outputs:
        if not isinstance(out, NASwebOutput):
            _LOGGER.error("Cannot create Output entity without NASwebOutput")
            continue
        new_output = Output(coordinator, out)
        entities.append(new_output)
    async_add_entities(entities)


class Output(CoordinatorEntity, SwitchEntity):
    """Entity representing NASweb Output."""

    def __init__(
        self, coordinator: NASwebCoordinator, nasweb_output: NASwebOutput
    ) -> None:
        """Initialize Output."""
        super().__init__(coordinator)
        self.coordinator: NASwebCoordinator
        self._output = nasweb_output
        self._attr_is_on = self._output.state
        self._attr_available = self._output.available
        self._attr_icon = "mdi:export"
        self._attr_has_entity_name = True
        self._attr_should_poll = False
        self._attr_translation_key = OUTPUT_TRANSLATION_KEY
        new_id = coordinator.webio_api.get_serial_number()
        if new_id is not None:
            self._attr_unique_id = f"{DOMAIN}.{new_id}.output.{self._output.index}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_is_on = self._output.state
        self._attr_available = self._output.available
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return DeviceInfo linking this Output with NASweb device."""
        device_serial = self.coordinator.webio_api.get_serial_number()
        if not device_serial:
            return None
        return DeviceInfo(
            identifiers={(DOMAIN, device_serial)},
        )

    @property
    def name(self) -> str:
        """Return name of output."""
        translated_name = super().name
        return f"{translated_name} {self._output.index:2d}"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn On Output."""
        await self._output.turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn Off Output."""
        await self._output.turn_off()
