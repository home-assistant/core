"""Platform for NASweb output."""

from __future__ import annotations

import logging
import time
from typing import Any

from webio_api import Output as NASwebOutput
from webio_api.const import KEY_OUTPUTS

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.helpers.entity_registry as er
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    BaseCoordinatorEntity,
    BaseDataUpdateCoordinatorProtocol,
)

from .const import DOMAIN, STATUS_UPDATE_MAX_TIME_INTERVAL
from .nasweb_data import NASwebData

OUTPUT_TRANSLATION_KEY = "switch_output"

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up switch platform."""
    nasweb_data: NASwebData = hass.data[DOMAIN]
    coordinator = nasweb_data.entries_coordinators[config.entry_id]
    nasweb_outputs = coordinator.data[KEY_OUTPUTS]
    entities: list[RelaySwitch] = []
    for out in nasweb_outputs:
        if not isinstance(out, NASwebOutput):
            _LOGGER.error("Cannot create RelaySwitch entity without NASwebOutput")
            continue
        new_output = RelaySwitch(coordinator, out)
        entities.append(new_output)
    async_add_entities(entities)


class RelaySwitch(SwitchEntity, BaseCoordinatorEntity):
    """Entity representing NASweb Output."""

    def __init__(
        self,
        coordinator: BaseDataUpdateCoordinatorProtocol,
        nasweb_output: NASwebOutput,
    ) -> None:
        """Initialize RelaySwitch."""
        super().__init__(coordinator)
        self._output = nasweb_output
        self._attr_icon = "mdi:export"
        self._attr_has_entity_name = True
        self._attr_translation_key = OUTPUT_TRANSLATION_KEY
        self._attr_translation_placeholders = {"index": f"{nasweb_output.index:2d}"}
        self._attr_unique_id = (
            f"{DOMAIN}.{self._output.webio_serial}.relay_switch.{self._output.index}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._output.webio_serial)},
        )

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        old_available = self.available
        self._attr_is_on = self._output.state
        if (
            self.coordinator.last_update is None
            or time.time() - self._output.last_update >= STATUS_UPDATE_MAX_TIME_INTERVAL
        ):
            self._attr_available = False
        else:
            self._attr_available = (
                self._output.available if self._output.available is not None else False
            )
        if old_available and self._output.available is None and self.unique_id:
            _LOGGER.warning("Removing entity: %s", self)
            entity_registry = er.async_get(self.hass)
            entity_registry.async_remove(self.entity_id)
            return
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the entity.

        Only used by the generic entity update service.
        """
        # return await super().async_update()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn On RelaySwitch."""
        await self._output.turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn Off RelaySwitch."""
        await self._output.turn_off()
