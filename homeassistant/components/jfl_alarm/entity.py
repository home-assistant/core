"""The entity base class and the discovery helper the platform uses.

Discovery has to be repeatable: a panel dials in ten to sixty seconds after Home Assistant starts,
so at setup time there is usually nothing to create. `async_add_discovered` therefore runs on every
coordinator update and adds only what is new.
"""

from typing import TYPE_CHECKING, cast, override

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import LOGGER
from .coordinator import JflPanelCoordinator, JflPanelState
from .device import build_panel_device, build_partition_device

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from homeassistant.helpers.entity import Entity
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback


class JflEntity(CoordinatorEntity[JflPanelCoordinator]):
    """Base for every entity in this integration."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: JflPanelCoordinator, key: str) -> None:
        """Bind to a panel's coordinator. *key* makes the unique id unique within that panel."""
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = f"{coordinator.serial}-{key}"
        self._attr_device_info = build_panel_device(
            coordinator.data.connection, coordinator.serial, coordinator.subentry.title
        )

    @property
    def snapshot(self) -> JflPanelState:
        """The panel's current state. Never `None`; an empty snapshot is a legitimate value.

        Deliberately **not** called `state`: `Entity.state` is Home Assistant's own property, the
        one that ends up in the state machine, and shadowing it makes every entity in the
        integration try to publish a dataclass as its state.
        """
        return self.coordinator.data

    @property
    @override
    def available(self) -> bool:
        """Availability follows the **connection**, not `last_update_success`.

        A coordinator that has never produced an update is not a panel in trouble — it is a panel
        that has not dialled in yet. What makes an entity unavailable is the socket going away,
        which the listener's watchdog reports.
        """
        return self.coordinator.data.available


class JflPartitionEntity(JflEntity):
    """An entity that belongs to one partition's sub-device."""

    def __init__(
        self, coordinator: JflPanelCoordinator, partition: int, key: str
    ) -> None:
        """Bind to *partition*, 1-based, on this panel.

        The programmed name is passed through if one is already known — see the note below on the
        defect that makes this necessary rather than merely tidy.
        """
        self.partition = partition
        super().__init__(coordinator, f"partition{partition}-{key}")
        # `build_partition_device` returns a plain dict, shaped as `DeviceInfo` pre-2026.9 and as
        # `ChildDeviceInfo` from 2026.9 on — `_attr_device_info`'s declared type is the former, but
        # Home Assistant itself only ever consumes both as a dict at the boundary in
        # `entity_platform.py`, so the cast is exactly as safe as the runtime behavior it describes.
        self._attr_device_info = cast(
            "DeviceInfo",
            build_partition_device(
                coordinator.hass,
                coordinator.config_entry.entry_id,
                coordinator.serial,
                partition,
                name=coordinator.programming.partition_name(partition),
            ),
        )


@callback
def async_add_discovered(
    coordinator: JflPanelCoordinator,
    async_add_entities: AddConfigEntryEntitiesCallback,
    discover: Callable[[JflPanelState], Iterable[Entity]],
) -> None:
    """Run *discover* now and again on every coordinator update.

    This is the helper that makes an inbound-connection integration work at all. At setup time the
    panel has usually not connected, so `discover` returns nothing; when the connection frame and
    the first status frame arrive it returns the real entity set, and it keeps being asked
    afterwards so a partition programmed later still appears.

    *discover* must be idempotent — it is called repeatedly and is expected to return only entities
    that do not exist yet. `JflPanelCoordinator.discovered` is the bookkeeping it uses.
    """

    @callback
    def _discover() -> None:
        new = list(discover(coordinator.data))
        if new:
            LOGGER.debug(
                "%s: adding %d entities discovered after connection",
                coordinator.serial,
                len(new),
            )
            async_add_entities(new, config_subentry_id=coordinator.subentry.subentry_id)

    coordinator.config_entry.async_on_unload(coordinator.async_add_listener(_discover))
    _discover()
