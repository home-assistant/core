"""Sandbox-side entity bridge — pushes registrations + state changes to main.

The bridge listens for ``EVENT_STATE_CHANGED`` on the sandbox-private
:class:`HomeAssistant`. First-time appearances (``old_state is None``)
trigger a ``sandbox/register_entity`` call up to main; subsequent
changes become ``sandbox/state_changed`` pushes.

We deliberately tag every event with the sandbox-side ``entry_id`` of
the owning :class:`EntityPlatform` so main can route each proxy entity
to the right :class:`ConfigEntry`. Entities that aren't owned by a
sandbox-managed entry (rare — typically helper-domain entities the
integration creates outside its own entry) are skipped with a debug log.
"""

import asyncio
from collections.abc import Iterable
import json
import logging
from typing import Any

from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import EVENT_DEVICE_REGISTRY_UPDATED
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import DATA_INSTANCES
from homeassistant.helpers.entity_registry import EVENT_ENTITY_REGISTRY_UPDATED

from ._proto import sandbox_pb2 as pb
from .approved_domains import ApprovedDomains
from .channel import Channel
from .messages import make_entity_description
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
        # Entities whose removal arrived while their register RPC was still
        # in flight. The register task flushes (unregisters) them once it
        # completes — relying on `_registered` membership would miss the
        # removal because the entity isn't registered yet at removal time.
        self._removed_while_pending: set[str] = set()
        # Hash of the last description (registry-shaped fields only, no
        # state) sent per entity, so a registry-update resend that mirrors
        # nothing we actually carry is a no-op instead of an event storm.
        self._last_hash: dict[str, str] = {}
        self._unsub_state: Any = None
        self._unsub_entity_registry: Any = None
        self._unsub_device_registry: Any = None

    def register(self, channel: Channel) -> None:
        """Subscribe to state + registry events and capture the channel."""
        self._channel = channel
        self._unsub_state = self.hass.bus.async_listen(
            EVENT_STATE_CHANGED, self._on_state_changed
        )
        # Post-registration changes to name / icon / category / device link
        # arrive as registry-updated events; re-send the registration as an
        # upsert so main's proxy keeps current.
        self._unsub_entity_registry = self.hass.bus.async_listen(
            EVENT_ENTITY_REGISTRY_UPDATED, self._on_entity_registry_updated
        )
        self._unsub_device_registry = self.hass.bus.async_listen(
            EVENT_DEVICE_REGISTRY_UPDATED, self._on_device_registry_updated
        )

    async def async_stop(self) -> None:
        """Detach the state + registry listeners."""
        for attr in (
            "_unsub_state",
            "_unsub_entity_registry",
            "_unsub_device_registry",
        ):
            unsub = getattr(self, attr)
            if unsub is not None:
                unsub()
                setattr(self, attr, None)

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
                    name=f"sandbox:unregister:{entity_id}",
                )
            elif entity_id in self._pending:
                # Removed mid-register: the register task hasn't added it to
                # _registered yet, so flag it and let that task unregister.
                self._removed_while_pending.add(entity_id)
            return

        if entity_id in self._registered:
            asyncio.create_task(  # noqa: RUF006
                self._push_state(entity_id, new_state),
                name=f"sandbox:state:{entity_id}",
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
            name=f"sandbox:register:{entity_id}",
        )

    @callback
    def _on_entity_registry_updated(self, event: Event[Any]) -> None:
        if self._channel is None or self._channel.closed:
            return
        if event.data.get("action") != "update":
            return
        entity_id: str = event.data["entity_id"]
        if entity_id not in self._registered:
            return
        asyncio.create_task(  # noqa: RUF006
            self._resend(entity_id),
            name=f"sandbox:resend:{entity_id}",
        )

    @callback
    def _on_device_registry_updated(self, event: Event[Any]) -> None:
        if self._channel is None or self._channel.closed:
            return
        if event.data.get("action") != "update":
            return
        device_id: str = event.data["device_id"]
        ent_reg = er.async_get(self.hass)
        # Re-send every tracked entity linked to the changed device so the
        # refreshed device_info reaches main.
        for entity_id in list(self._registered):
            registry_entry = ent_reg.async_get(entity_id)
            if registry_entry is None or registry_entry.device_id != device_id:
                continue
            asyncio.create_task(  # noqa: RUF006
                self._resend(entity_id),
                name=f"sandbox:resend:{entity_id}",
            )

    async def _register_and_push(self, entity_id: str, new_state: Any) -> None:
        try:
            await self._register(entity_id, new_state)
        finally:
            self._pending.discard(entity_id)

        # While the register RPC was in flight, _on_state_changed dropped any
        # further state_changed for this entity (it was neither registered nor
        # re-queued). Reconcile that coalesced gap now.
        #
        # NOTE: this is the *correctness* fix. Plan 5 (simplification) builds a
        # single-writer queue on top of the entity push path; when it lands it
        # should subsume this flush into the queue's ordering guarantees.
        if entity_id in self._removed_while_pending:
            # A removal raced the register. Now that register has completed
            # (and added the entity to _registered), unregister it so main
            # doesn't keep a ghost proxy.
            self._removed_while_pending.discard(entity_id)
            if entity_id in self._registered:
                self._registered.discard(entity_id)
                self._last_hash.pop(entity_id, None)
                await self._push_unregister(entity_id)
            return

        if entity_id not in self._registered:
            # Register failed (or was skipped); nothing to flush.
            return

        current = self.hass.states.get(entity_id)
        if current is None:
            return
        if _state_differs(current, new_state):
            await self._push_state(entity_id, current)

    def _describe(self, entity_id: str) -> dict[str, Any] | None:
        """Build the registry-shaped description for a live entity, or None."""
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
            return None
        entry_id = _entry_id_for(entity)
        if entry_id is None:
            _LOGGER.debug(
                "EntityBridge: %s has no owning config entry; not bridging",
                entity_id,
            )
            return None
        return _describe_entity(entity, entry_id)

    async def _register(self, entity_id: str, new_state: Any) -> None:
        if self._channel is None:
            return
        payload = self._describe(entity_id)
        if payload is None:
            return
        new_hash = _payload_hash(payload)
        initial_state = None
        initial_attributes = None
        if hasattr(new_state, "state"):
            initial_state = new_state.state
            initial_attributes = dict(new_state.attributes)
        try:
            await self._channel.call(
                MSG_REGISTER_ENTITY,
                _to_entity_description(payload, initial_state, initial_attributes),
            )
        except Exception:
            _LOGGER.exception("EntityBridge: register failed for %s", entity_id)
            return
        self._registered.add(entity_id)
        self._last_hash[entity_id] = new_hash
        # Approve the entity's domain so the service + event mirrors
        # let through registrations / events that originate from it.
        self.approved.add(payload["domain"])

    async def _resend(self, entity_id: str) -> None:
        """Re-send a registration as an upsert after a registry change.

        Skips when the entity isn't tracked yet (the initial register will
        carry current values) or when nothing we mirror actually changed.
        """
        if self._channel is None or self._channel.closed:
            return
        if entity_id not in self._registered:
            return
        payload = self._describe(entity_id)
        if payload is None:
            return
        new_hash = _payload_hash(payload)
        if self._last_hash.get(entity_id) == new_hash:
            return
        initial_state = None
        initial_attributes = None
        state = self.hass.states.get(entity_id)
        if state is not None:
            initial_state = state.state
            initial_attributes = dict(state.attributes)
        try:
            await self._channel.call(
                MSG_REGISTER_ENTITY,
                _to_entity_description(payload, initial_state, initial_attributes),
            )
        except Exception:
            _LOGGER.exception("EntityBridge: resend failed for %s", entity_id)
            return
        self._last_hash[entity_id] = new_hash

    async def _push_state(self, entity_id: str, new_state: Any) -> None:
        if self._channel is None:
            return
        msg = pb.StateChanged(sandbox_entity_id=entity_id)
        if new_state.state is not None:
            msg.state = new_state.state
        msg.attributes.update(dict(new_state.attributes))
        # Forward only the context id — never parent_id / user_id. Main
        # resolves it to a Context attributed to the sandbox system user.
        context = getattr(new_state, "context", None)
        if context is not None and context.id:
            msg.context_id = context.id
        try:
            await self._channel.push(MSG_STATE_CHANGED, msg)
        except Exception:
            _LOGGER.exception("EntityBridge: state push failed for %s", entity_id)

    async def _push_unregister(self, entity_id: str) -> None:
        if self._channel is None:
            return
        try:
            await self._channel.call(
                MSG_UNREGISTER_ENTITY, pb.UnregisterEntity(sandbox_entity_id=entity_id)
            )
        except Exception:
            _LOGGER.exception("EntityBridge: unregister failed for %s", entity_id)


def _to_entity_description(
    payload: dict[str, Any],
    initial_state: str | None,
    initial_attributes: dict[str, Any] | None,
) -> pb.EntityDescription:
    """Build the typed ``EntityDescription`` message from a describe dict."""
    return make_entity_description(
        entry_id=payload["entry_id"],
        domain=payload["domain"],
        sandbox_entity_id=payload["sandbox_entity_id"],
        unique_id=payload.get("unique_id"),
        name=payload.get("name"),
        icon=payload.get("icon"),
        has_entity_name=bool(payload.get("has_entity_name", False)),
        entity_category=payload.get("entity_category"),
        device_class=payload.get("device_class"),
        supported_features=int(payload.get("supported_features") or 0),
        capabilities=payload.get("capabilities"),
        initial_state=initial_state,
        initial_attributes=initial_attributes,
        device_info=payload.get("device_info"),
    )


def _state_differs(current: Any, snapshot: Any) -> bool:
    """Whether ``current`` state/attributes differ from the registered snapshot.

    ``snapshot`` is the ``new_state`` captured when the register task was
    created; ``current`` is the live state re-read after the register RPC
    resolved. A difference means a state change was coalesced away during the
    in-flight window and must be flushed.
    """
    snap_state = getattr(snapshot, "state", None)
    snap_attrs = dict(snapshot.attributes) if hasattr(snapshot, "attributes") else {}
    return current.state != snap_state or dict(current.attributes) != snap_attrs


def _payload_hash(payload: dict[str, Any]) -> str:
    """Stable hash of a description payload's mirrored fields.

    State-shaped keys (``initial_state`` / ``initial_attributes``) flow via
    the ``state_changed`` push path and are excluded so the resend guard
    only fires on changes to fields a registration actually carries.
    """
    mirrored = {
        key: value
        for key, value in payload.items()
        if key not in ("initial_state", "initial_attributes")
    }
    return json.dumps(mirrored, sort_keys=True, default=str)


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
    payload: dict[str, Any] = {
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
    device_info = _serialise_device_info(entity.device_info)
    if device_info is not None:
        payload["device_info"] = device_info
    return payload


def _serialise_device_info(device_info: Any) -> dict[str, Any] | None:
    """Return a JSON-safe rendering of an entity's ``device_info``.

    ``DeviceInfo`` is a ``TypedDict`` with set/tuple-shaped fields
    (``identifiers``, ``connections``, ``via_device``) and a ``StrEnum``
    (``entry_type``). Sets become lists of two-element lists (preserving
    the pair shape main needs to rebuild tuples); enums become their
    string value; ``URL`` instances become strings. Anything else passes
    through ``_serialise`` for generic JSON-safety.
    """
    if not device_info:
        return None
    if not isinstance(device_info, dict):
        return None
    out: dict[str, Any] = {}
    for key, value in device_info.items():
        if value is None:
            out[key] = None
            continue
        if key in ("identifiers", "connections"):
            # set[tuple[str, str]] → list[list[str, str]]
            out[key] = [list(item) for item in value]
        elif key == "via_device":
            # tuple[str, str] → list[str]
            out[key] = list(value)
        elif key == "entry_type":
            out[key] = getattr(value, "value", str(value))
        elif key == "configuration_url":
            out[key] = str(value) if value is not None else None
        else:
            out[key] = _serialise(value)
    return out


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
