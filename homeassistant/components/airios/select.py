"""Select platform for the Airios integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any, cast

from pyairios import VMD02RPS78, ProductId
from pyairios.constants import VMDBypassMode
from pyairios.data_model import AiriosNodeData
from pyairios.exceptions import AiriosException

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_SLAVE
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, PlatformNotReady
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AiriosDataUpdateCoordinator
from .entity import AiriosEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class AiriosSelectEntityDescription(SelectEntityDescription):
    """Airios select description."""

    value_fn: Callable[[Any], str | None] | None = None


BYPASS_MODE_TO_NAME: dict[VMDBypassMode, str] = {
    VMDBypassMode.OPEN: "open",
    VMDBypassMode.CLOSE: "close",
    VMDBypassMode.AUTO: "auto",
    VMDBypassMode.UNKNOWN: "unknown",
}
NAME_TO_BYPASS_MODE = {value: key for (key, value) in BYPASS_MODE_TO_NAME.items()}


def bypass_mode_value_fn(v: VMDBypassMode) -> str | None:
    """Convert bypass mode to select's value."""
    return BYPASS_MODE_TO_NAME.get(v)


VMD_SELECT_ENTITIES: tuple[AiriosSelectEntityDescription, ...] = (
    AiriosSelectEntityDescription(
        key="bypass_mode",
        translation_key="bypass_mode",
        options=["close", "open", "auto"],
        value_fn=bypass_mode_value_fn,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the selectors."""

    coordinator: AiriosDataUpdateCoordinator = entry.runtime_data

    for slave_id, node in coordinator.data.nodes.items():
        # Find matching subentry
        subentry_id = None
        subentry = None
        via = None
        for se_id, se in entry.subentries.items():
            if se.data[CONF_SLAVE] == slave_id:
                subentry_id = se_id
                subentry = se
                via = entry

        entities: list[AiriosSelectEntity] = []
        if node["product_id"] is None or node["product_id"].value is None:
            raise PlatformNotReady("Nde product ID not available")

        if node["product_id"].value == ProductId.VMD_02RPS78:
            entities.extend(
                [
                    AiriosSelectEntity(description, coordinator, node, via, subentry)
                    for description in VMD_SELECT_ENTITIES
                ]
            )
        async_add_entities(entities, config_subentry_id=subentry_id)


class AiriosSelectEntity(AiriosEntity, SelectEntity):
    """Airios select entity."""

    entity_description: AiriosSelectEntityDescription

    def __init__(
        self,
        description: AiriosSelectEntityDescription,
        coordinator: AiriosDataUpdateCoordinator,
        node: AiriosNodeData,
        via_config_entry: ConfigEntry | None,
        subentry: ConfigSubentry | None,
    ) -> None:
        """Initialize a Airios select entity."""

        super().__init__(description.key, coordinator, node, via_config_entry, subentry)
        self.entity_description = description
        self._attr_current_option = None

    async def _select_option_internal(self, option: str) -> bool:
        if option == self.current_option:
            return False

        try:
            node = cast(VMD02RPS78, await self.api().node(self.slave_id))
            bypass_mode = NAME_TO_BYPASS_MODE[option]
            ret = await node.set_bypass_mode(bypass_mode)
        except AiriosException as ex:
            raise HomeAssistantError(f"Failed to set bypass mode {option}") from ex
        else:
            return ret

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        update_needed = await self._select_option_internal(option)
        if update_needed:
            await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle update data from the coordinator."""
        _LOGGER.debug(
            "Handle update for node %s select %s",
            f"{self.rf_address}",
            self.entity_description.key,
        )
        try:
            device = self.coordinator.data.nodes[self.slave_id]
            result = device[self.entity_description.key]
            _LOGGER.debug(
                "Node %s, select %s, result %s",
                f"0x{self.rf_address:08X}",
                self.entity_description.key,
                result,
            )
            if result is not None and result.value is not None:
                if self.entity_description.value_fn:
                    self._attr_current_option = self.entity_description.value_fn(
                        result.value
                    )
                else:
                    self._attr_current_option = result.value
                self._attr_available = self._attr_current_option is not None
                if result.status is not None:
                    self.set_extra_state_attributes_internal(result.status)
        except (TypeError, ValueError) as ex:
            _LOGGER.error(
                "Failed to update node %s select %s: %s",
                f"0x{self.rf_address:08X}",
                self.entity_description.key,
                ex,
            )
            self._attr_current_option = None
            self._attr_available = False
        finally:
            self.async_write_ha_state()
