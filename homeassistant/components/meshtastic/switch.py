"""Support for Meshtastic settings that are switches.

Only the LoRa and device settings the firmware applies live are here; see
``config_entity`` for the reboot matrix that decides what may be exposed.  The
per-node favourite and ignored flags are node-database writes
(``set_favorite_node`` / ``set_ignored_node``), which the firmware saves with
``saveChanges(SEGMENT_NODEDATABASE, false)`` and therefore never reboot.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MeshtasticConfigEntry
from .config_entity import (
    SECTION_DEVICE,
    SECTION_LORA,
    MeshtasticConfigEntity,
    MeshtasticConfigSnapshot,
    async_get_config_snapshot,
    async_send_admin,
)
from .coordinator import MeshtasticCoordinator
from .entity import MeshtasticNodeEntity
from .models import MeshtasticNode

# Every write goes to the radio, which serves one admin message at a time.
PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class MeshtasticSwitchEntityDescription(SwitchEntityDescription):
    """Describes a Meshtastic gateway configuration switch."""

    section: str
    field: str


@dataclass(frozen=True, kw_only=True)
class MeshtasticNodeSwitchEntityDescription(SwitchEntityDescription):
    """Describes a per-node flag in the gateway's node database."""

    value_fn: Callable[[MeshtasticNode], bool]
    #: ``meshtastic.node.Node`` methods that set and clear the flag.
    set_method: str
    clear_method: str


GATEWAY_SWITCHES: tuple[MeshtasticSwitchEntityDescription, ...] = (
    MeshtasticSwitchEntityDescription(
        key="lora_tx_enabled",
        translation_key="lora_tx_enabled",
        section=SECTION_LORA,
        field="tx_enabled",
    ),
    MeshtasticSwitchEntityDescription(
        key="lora_ignore_mqtt",
        translation_key="lora_ignore_mqtt",
        section=SECTION_LORA,
        field="ignore_mqtt",
    ),
    MeshtasticSwitchEntityDescription(
        key="lora_config_ok_to_mqtt",
        translation_key="lora_config_ok_to_mqtt",
        section=SECTION_LORA,
        field="config_ok_to_mqtt",
        entity_registry_enabled_default=False,
    ),
    MeshtasticSwitchEntityDescription(
        key="lora_override_duty_cycle",
        translation_key="lora_override_duty_cycle",
        section=SECTION_LORA,
        field="override_duty_cycle",
        entity_registry_enabled_default=False,
    ),
    MeshtasticSwitchEntityDescription(
        key="device_led_heartbeat_disabled",
        translation_key="device_led_heartbeat_disabled",
        section=SECTION_DEVICE,
        field="led_heartbeat_disabled",
        entity_registry_enabled_default=False,
    ),
)

NODE_SWITCHES: tuple[MeshtasticNodeSwitchEntityDescription, ...] = (
    MeshtasticNodeSwitchEntityDescription(
        key="favorite",
        translation_key="favorite",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda node: node.is_favorite,
        set_method="setFavorite",
        clear_method="removeFavorite",
    ),
    MeshtasticNodeSwitchEntityDescription(
        key="ignored",
        translation_key="ignored",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda node: node.is_ignored,
        set_method="setIgnored",
        clear_method="removeIgnored",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MeshtasticConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Meshtastic switches from a config entry."""
    coordinator = entry.runtime_data.coordinator
    snapshot = await async_get_config_snapshot(entry)
    async_add_entities(
        MeshtasticConfigSwitch(coordinator, snapshot, description)
        for description in GATEWAY_SWITCHES
    )

    known: set[str] = set()

    @callback
    def _check_nodes() -> None:
        """Add the flag switches of every mesh node that introduced itself."""
        new = {
            node_id
            for node_id, node in coordinator.data.nodes.items()
            if node_id not in known
            and not node.presumptive
            and node.num != coordinator.gateway.node_num
        }
        if not new:
            return
        known.update(new)
        async_add_entities(
            MeshtasticNodeFlagSwitch(
                coordinator, coordinator.data.nodes[node_id], description
            )
            for node_id in new
            for description in NODE_SWITCHES
        )

    _check_nodes()
    entry.async_on_unload(coordinator.async_add_listener(_check_nodes))


class MeshtasticConfigSwitch(MeshtasticConfigEntity, SwitchEntity):
    """A gateway setting the firmware applies without rebooting."""

    entity_description: MeshtasticSwitchEntityDescription

    def __init__(
        self,
        coordinator: MeshtasticCoordinator,
        snapshot: MeshtasticConfigSnapshot,
        description: MeshtasticSwitchEntityDescription,
    ) -> None:
        """Initialise a gateway configuration switch."""
        super().__init__(
            coordinator,
            snapshot,
            key=description.key,
            section=description.section,
            field=description.field,
        )
        self.entity_description = description

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether the setting is enabled on the node."""
        value = self.config_value
        return None if value is None else bool(value)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the setting."""
        await self._async_set(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the setting."""
        await self._async_set(False)

    async def _async_set(self, value: bool) -> None:
        """Write one boolean and show it only once the node acknowledged it."""
        await self.async_write_config(value)
        self.async_write_ha_state()


class MeshtasticNodeFlagSwitch(MeshtasticNodeEntity, SwitchEntity):
    """A favourite or ignored flag in the gateway's node database."""

    entity_description: MeshtasticNodeSwitchEntityDescription

    def __init__(
        self,
        coordinator: MeshtasticCoordinator,
        node: MeshtasticNode,
        description: MeshtasticNodeSwitchEntityDescription,
    ) -> None:
        """Initialise a node flag switch."""
        super().__init__(coordinator, node, description.key)
        self.entity_description = description
        self._assumed: bool | None = None

    @property
    def _reported(self) -> bool | None:
        """Return the flag as the gateway's node database last reported it."""
        if (node := self.node) is None:
            return None
        return self.entity_description.value_fn(node)

    @property
    @override
    def is_on(self) -> bool | None:
        """Return whether the flag is set for this node.

        The node database only republishes flags when the gateway pushes a
        record, so an acknowledged write is shown until the gateway agrees.
        """
        if self._assumed is not None:
            return self._assumed
        return self._reported

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Drop the assumed value once the gateway reports the same thing."""
        if self._assumed is not None and self._reported == self._assumed:
            self._assumed = None
        super()._handle_coordinator_update()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Set the flag for this node."""
        await self._async_set(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Clear the flag for this node."""
        await self._async_set(False)

    async def _async_set(self, value: bool) -> None:
        """Write the flag and reflect it once the node acknowledged it."""
        description = self.entity_description
        method = description.set_method if value else description.clear_method
        node_num = self.node_num

        def _send(interface: Any) -> Any:
            return getattr(interface.localNode, method)(node_num)

        await async_send_admin(self.coordinator, _send)
        self._assumed = value
        self.async_write_ha_state()
