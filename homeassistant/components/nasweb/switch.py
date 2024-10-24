"""Platform for NASweb output."""

from __future__ import annotations

import logging
import time
from typing import Any

from webio_api import Output as NASwebOutput

from homeassistant.components.switch import DOMAIN as DOMAIN_SWITCH, SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.helpers.entity_registry as er
from homeassistant.helpers.typing import DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    BaseCoordinatorEntity,
    BaseDataUpdateCoordinatorProtocol,
)

from . import NASwebConfigEntry
from .const import DOMAIN, STATUS_UPDATE_MAX_TIME_INTERVAL
from .coordinator import NASwebCoordinator

OUTPUT_TRANSLATION_KEY = "switch_output"

_LOGGER = logging.getLogger(__name__)


def _get_output(coordinator: NASwebCoordinator, index: int) -> NASwebOutput | None:
    for out in coordinator.webio_api.outputs:
        if out.index == index:
            return out
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    config: NASwebConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up switch platform."""
    coordinator = config.runtime_data
    current_outputs: set[int] = set()

    @callback
    def _check_entities() -> None:
        received_outputs = {out.index for out in coordinator.webio_api.outputs}
        added = {i for i in received_outputs if i not in current_outputs}
        removed = {i for i in current_outputs if i not in received_outputs}
        entities_to_add: list[RelaySwitch] = []
        for index in added:
            webio_output = _get_output(coordinator, index)
            if not isinstance(webio_output, NASwebOutput):
                _LOGGER.error("Cannot create RelaySwitch entity without NASwebOutput")
                continue
            new_output = RelaySwitch(coordinator, webio_output)
            entities_to_add.append(new_output)
            current_outputs.add(index)
        async_add_entities(entities_to_add)
        entity_registry = er.async_get(hass)
        for index in removed:
            unique_id = f"{DOMAIN}.{config.unique_id}.relay_switch.{index}"
            if entity_id := entity_registry.async_get_entity_id(
                DOMAIN_SWITCH, DOMAIN, unique_id
            ):
                entity_registry.async_remove(entity_id)
                current_outputs.remove(index)
            else:
                _LOGGER.warning("Failed to remove old output: no entity_id")

    coordinator.async_add_listener(_check_entities)
    _check_entities()


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
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Update the entity.

        Only used by the generic entity update service.
        Scheduling updates is not necessary, the coordinator takes care of updates via push notifications.
        """

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn On RelaySwitch."""
        await self._output.turn_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn Off RelaySwitch."""
        await self._output.turn_off()
