"""Select for Shelly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from aioshelly.const import RPC_GENERATIONS

from homeassistant.components.select import (
    DOMAIN as SELECT_PLATFORM,
    SelectEntity,
    SelectEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ROLE_GENERIC
from .coordinator import ShellyConfigEntry, ShellyRpcCoordinator
from .entity import (
    RpcEntityDescription,
    ShellyRpcAttributeEntity,
    async_setup_entry_rpc,
    rpc_call,
)
from .utils import (
    async_remove_orphaned_entities,
    get_device_entry_gen,
    get_virtual_component_ids,
    is_view_for_platform,
)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class RpcSelectDescription(RpcEntityDescription, SelectEntityDescription):
    """Class to describe a RPC select entity."""

    method: str


class RpcSelect(ShellyRpcAttributeEntity, SelectEntity):
    """Represent a RPC select entity."""

    entity_description: RpcSelectDescription
    _id: int

    def __init__(
        self,
        coordinator: ShellyRpcCoordinator,
        key: str,
        attribute: str,
        description: RpcSelectDescription,
    ) -> None:
        """Initialize select."""
        super().__init__(coordinator, key, attribute, description)

        if self.option_map:
            self._attr_options = list(self.option_map.values())

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        if isinstance(self.attribute_value, str) and self.option_map:
            return self.option_map[self.attribute_value]

        return None

    @rpc_call
    async def async_select_option(self, option: str) -> None:
        """Change the value."""
        method = getattr(self.coordinator.device, self.entity_description.method)

        if TYPE_CHECKING:
            assert method is not None

        if self.reversed_option_map:
            await method(self._id, self.reversed_option_map[option])
        else:
            await method(self._id, option)


class RpcCuryModeSelect(RpcSelect):
    """Represent a RPC select entity for Cury modes."""

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        if self.attribute_value is None:
            return "none"

        if TYPE_CHECKING:
            assert isinstance(self.attribute_value, str)

        return self.attribute_value


RPC_SELECT_ENTITIES: Final = {
    "cury_mode": RpcSelectDescription(
        key="cury",
        sub_key="mode",
        translation_key="cury_mode",
        options=[
            "hall",
            "bedroom",
            "living_room",
            "lavatory_room",
            "none",
            "reception",
            "workplace",
        ],
        method="cury_set_mode",
        entity_class=RpcCuryModeSelect,
    ),
    "enum_generic": RpcSelectDescription(
        key="enum",
        sub_key="value",
        removal_condition=lambda config, _status, key: not is_view_for_platform(
            config, key, SELECT_PLATFORM
        ),
        method="enum_set",
        role=ROLE_GENERIC,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ShellyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up select entities."""
    if get_device_entry_gen(config_entry) in RPC_GENERATIONS:
        return _async_setup_rpc_entry(hass, config_entry, async_add_entities)

    return None


@callback
def _async_setup_rpc_entry(
    hass: HomeAssistant,
    config_entry: ShellyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entities for RPC device."""
    coordinator = config_entry.runtime_data.rpc
    assert coordinator

    async_setup_entry_rpc(
        hass, config_entry, async_add_entities, RPC_SELECT_ENTITIES, RpcSelect
    )

    # the user can remove virtual components from the device configuration, so
    # we need to remove orphaned entities
    virtual_text_ids = get_virtual_component_ids(
        coordinator.device.config, SELECT_PLATFORM
    )
    async_remove_orphaned_entities(
        hass,
        config_entry.entry_id,
        coordinator.mac,
        SELECT_PLATFORM,
        virtual_text_ids,
        "enum",
    )
