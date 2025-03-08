"""Button platform for the Airios integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import cast

from pyairios import AiriosException
from pyairios.constants import ProductId
from pyairios.data_model import AiriosNodeData
from pyairios.node import AiriosNode
from pyairios.vmd_02rps78 import VMD02RPS78

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_SLAVE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VMDEntityFeature
from .coordinator import AiriosDataUpdateCoordinator
from .entity import AiriosEntity
from .services import SERVICE_FILTER_RESET

_LOGGER = logging.getLogger(__name__)


async def _filter_reset(node: AiriosNode) -> bool:
    vmd = cast(VMD02RPS78, node)
    return await vmd.filter_reset()


@dataclass(frozen=True, kw_only=True)
class AiriosButtonEntityDescription(ButtonEntityDescription):
    """Airios binary sensor description."""

    press_fn: Callable[[AiriosNode], Awaitable[bool]]
    supported_features: VMDEntityFeature | None = None


VMD_BUTTON_ENTITIES: tuple[AiriosButtonEntityDescription, ...] = (
    AiriosButtonEntityDescription(
        key="filter_reset",
        translation_key="filter_reset",
        device_class=ButtonDeviceClass.RESTART,
        supported_features=VMDEntityFeature.FILTER_RESET,
        press_fn=_filter_reset,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the button platform."""

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

        entities: list[AiriosButtonEntity] = []

        result = node["product_id"]
        if result is None or result.value is None:
            raise ConfigEntryNotReady("Failed to fetch product id from node")
        if result.value == ProductId.VMD_02RPS78:
            entities.extend(
                [
                    AiriosButtonEntity(description, coordinator, node, via, subentry)
                    for description in VMD_BUTTON_ENTITIES
                ]
            )
        async_add_entities(entities, config_subentry_id=subentry_id)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_FILTER_RESET,
        None,
        "async_filter_reset",
        required_features=[VMDEntityFeature.FILTER_RESET],
    )


class AiriosButtonEntity(AiriosEntity, ButtonEntity):
    """Representation of a Airios button entity."""

    entity_description: AiriosButtonEntityDescription

    def __init__(
        self,
        description: AiriosButtonEntityDescription,
        coordinator: AiriosDataUpdateCoordinator,
        node: AiriosNodeData,
        via_config_entry: ConfigEntry | None,
        subentry: ConfigSubentry | None,
    ) -> None:
        """Initialize the Airios button entity."""
        super().__init__(description.key, coordinator, node, via_config_entry, subentry)
        self.entity_description = description
        self._attr_supported_features = description.supported_features

    async def async_press(self) -> None:
        """Handle button press."""
        _LOGGER.debug("Button %s pressed", self.entity_description.name)
        try:
            node = await self.api().node(self.slave_id)
            await self.entity_description.press_fn(node)
        except AiriosException as ex:
            raise HomeAssistantError from ex
