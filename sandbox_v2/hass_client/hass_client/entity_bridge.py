"""Sandbox-side entity bridge — pushes registrations + state changes to main.

The bridge listens for ``EVENT_STATE_CHANGED`` on the sandbox-private
:class:`HomeAssistant`. First-time appearances (``old_state is None``)
trigger a ``sandbox_v2/register_entity`` call up to main; subsequent
changes become ``sandbox_v2/state_changed`` pushes.

We deliberately tag every event with the sandbox-side ``entry_id`` of
the owning :class:`EntityPlatform` so main can route each proxy entity
to the right :class:`ConfigEntry`. Entities that aren't owned by a
sandbox-managed entry (rare — typically helper-domain entities the
integration creates outside its own entry) are skipped with a debug log.
"""

import asyncio
from collections.abc import Iterable
import logging
from typing import Any

from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import DATA_INSTANCES

from .approved_domains import ApprovedDomains
from .channel import Channel
from .protocol import MSG_REGISTER_ENTITY, MSG_STATE_CHANGED, MSG_UNREGISTER_ENTITY

_LOGGER = logging.getLogger(__name__)


class EntityBridge:
    """Forwards sandbox-side entity lifecycle events up to main.

    One instance per sandbox process (channel). It does not own the
    integration code — it just observes ``EVENT_STATE_CHANGED`` and
    inspects the matching ``EntityComponent`` to extract the rich shape
    that a proxy entity on main needs (capability dict, supported
    features, entity category, …).
    """

    def __init__(
        self, hass: HomeAssistant, approved: ApprovedDomains | None = None
    ) -> None:
        """Initialise with the sandbox-private HA instance.

        ``approved`` is shared with the service + event mirrors so the
        entity's domain becomes approved as soon as the first entity of
        that domain registers (the plan's *light is approved if a
        sandboxed integration registers light entities* clause).
        """
        self.hass = hass
        self.approved = approved if approved is not None else ApprovedDomains()
        self._channel: Channel | None = None
        self._registered: set[str] = set()
        self._pending: set[str] = set()
        self._unsub_state: Any = None

    def register(self, channel: Channel) -> None:
        """Subscribe to state-change events and capture the channel."""
        self._channel = channel
        self._unsub_state = self.hass.bus.async_listen(
            EVENT_STATE_CHANGED, self._on_state_changed
        )

    async def async_stop(self) -> None:
        """Detach the state listener."""
        if self._unsub_state is not None:
            self._unsub_state()
            self._unsub_state = None

    @callback
    def _on_state_changed(self, event: Event[EventStateChangedData]) -> None:
        if self._channel is None or self._channel.closed:
            return
        entity_id: str = event.data["entity_id"]
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")

        if new_state is None:
            if entity_id in self._registered:
                self._registered.discard(entity_id)
                asyncio.create_task(  # noqa: RUF006
                    self._push_unregister(entity_id),
                    name=f"sandbox_v2:unregister:{entity_id}",
                )
            return

        if entity_id in self._registered:
            asyncio.create_task(  # noqa: RUF006
                self._push_state(entity_id, new_state),
                name=f"sandbox_v2:state:{entity_id}",
            )
            return

        if old_state is not None and entity_id not in self._pending:
            # Existed before we started watching; register it now anyway.
            pass

        if entity_id in self._pending:
            return
        self._pending.add(entity_id)
        asyncio.create_task(  # noqa: RUF006
            self._register_and_push(entity_id, new_state),
            name=f"sandbox_v2:register:{entity_id}",
        )

    async def _register_and_push(self, entity_id: str, new_state: Any) -> None:
        try:
            await self._register(entity_id, new_state)
        finally:
            self._pending.discard(entity_id)

    async def _register(self, entity_id: str, new_state: Any) -> None:
        if self._channel is None:
            return
        domain = entity_id.split(".", 1)[0]
        components = self.hass.data.get(DATA_INSTANCES, {})
        component = components.get(domain)
        entity = component.get_entity(entity_id) if component is not None else None
        if entity is None:
            _LOGGER.debug(
                "EntityBridge: %s appeared in state machine but has no live"
                " entity object; skipping",
                entity_id,
            )
            return
        entry_id = _entry_id_for(entity)
        if entry_id is None:
            _LOGGER.debug(
                "EntityBridge: %s has no owning config entry; not bridging",
                entity_id,
            )
            return
        payload = _describe_entity(entity, entry_id)
        if hasattr(new_state, "state"):
            payload["initial_state"] = new_state.state
            payload["initial_attributes"] = dict(new_state.attributes)
        try:
            await self._channel.call(MSG_REGISTER_ENTITY, payload)
        except Exception:
            _LOGGER.exception("EntityBridge: register failed for %s", entity_id)
            return
        self._registered.add(entity_id)
        # Approve the entity's domain so the service + event mirrors
        # let through registrations / events that originate from it.
        self.approved.add(payload["domain"])

    async def _push_state(self, entity_id: str, new_state: Any) -> None:
        if self._channel is None:
            return
        payload = {
            "sandbox_entity_id": entity_id,
            "new_state": {
                "state": new_state.state,
                "attributes": dict(new_state.attributes),
            },
        }
        try:
            await self._channel.push(MSG_STATE_CHANGED, payload)
        except Exception:
            _LOGGER.exception("EntityBridge: state push failed for %s", entity_id)

    async def _push_unregister(self, entity_id: str) -> None:
        if self._channel is None:
            return
        try:
            await self._channel.call(
                MSG_UNREGISTER_ENTITY, {"sandbox_entity_id": entity_id}
            )
        except Exception:
            _LOGGER.exception(
                "EntityBridge: unregister failed for %s", entity_id
            )


def _entry_id_for(entity: Entity) -> str | None:
    """Return the entity's owning config-entry id, or None."""
    registry_entry = entity.registry_entry
    if registry_entry is not None and registry_entry.config_entry_id is not None:
        return registry_entry.config_entry_id
    platform = entity.platform
    if platform is not None and platform.config_entry is not None:
        return platform.config_entry.entry_id
    return None


def _describe_entity(entity: Entity, entry_id: str) -> dict[str, Any]:
    """Build a wire payload describing ``entity`` for ``register_entity``."""
    platform = entity.platform
    domain = platform.domain if platform is not None else entity.entity_id.split(".")[0]
    capabilities = _serialise(entity.capability_attributes or {})
    entity_category = entity.entity_category
    return {
        "entry_id": entry_id,
        "domain": domain,
        "sandbox_entity_id": entity.entity_id,
        "unique_id": entity.unique_id,
        "name": _stringify(entity.name),
        "icon": _stringify(entity.icon),
        "has_entity_name": bool(entity.has_entity_name),
        "entity_category": (
            entity_category.value if entity_category is not None else None
        ),
        "device_class": entity.device_class,
        "supported_features": int(entity.supported_features or 0),
        "capabilities": capabilities,
    }


def _stringify(value: Any) -> str | None:
    """Coerce a name/icon-style value into a plain string."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _serialise(value: Any) -> Any:
    """JSON-safe recursive coercion for capability dicts."""
    if isinstance(value, dict):
        return {str(k): _serialise(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_serialise(v) for v in _iter(value)]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, (str, int, float, bool)):
        return enum_value
    return str(value)


def _iter(value: Any) -> Iterable[Any]:
    """Stable iteration order for sets/frozensets."""
    if isinstance(value, (set, frozenset)):
        try:
            return sorted(value)
        except TypeError:
            return list(value)
    return value


__all__ = ["EntityBridge"]
