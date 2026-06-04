"""Sandbox — run integrations in isolated subprocesses.

The integration owns three runtime objects, all hung off
:class:`SandboxData`:

* :class:`SandboxManager` — supervises one subprocess per sandbox group
  ("main", "built-in", "custom"), lazily spawning them on first need.
* :class:`SandboxFlowRouter` — installed as
  ``hass.config_entries.router`` (Phase 4). Diverts new config flows to
  sandbox runtimes and routes ``async_setup_entry`` for tagged entries.
* :class:`SandboxBridge` (one per running sandbox) — owns the entity-side
  protocol: receives ``register_entity`` + ``state_changed`` pushes from
  the sandbox, instantiates proxy entities, and forwards entity service
  calls back via the shared ``sandbox/call_service`` channel.
"""

from dataclasses import dataclass, field
import logging
from typing import Any

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from ._proto import sandbox_pb2 as pb
from .bridge import SandboxBridge, async_create_bridge
from .channel import Channel
from .const import DATA_SANDBOX, DOMAIN
from .manager import SandboxManager
from .router import SandboxFlowRouter

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


@dataclass
class SandboxData:
    """Global Sandbox runtime data."""

    manager: SandboxManager | None = None
    router: SandboxFlowRouter | None = None
    channels: dict[str, Channel] = field(default_factory=dict)
    bridges: dict[str, SandboxBridge] = field(default_factory=dict)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Sandbox integration."""
    data = SandboxData()
    hass.data[DATA_SANDBOX] = data

    def _on_channel_ready(group: str, channel: Channel) -> None:
        # Drop any prior bridge for this group (a sandbox restart hands us
        # a fresh channel — the previous bridge owned the dead one).
        data.channels[group] = channel
        data.bridges[group] = async_create_bridge(hass, group=group, channel=channel)

    async def _on_shutdown_reply(group: str, reply: Any) -> None:
        """Persist the sandbox's restore-state snapshot (Phase 9).

        The runtime ships its ``RestoreEntity`` state in the shutdown
        reply (a ``ShutdownResult``) rather than via the sandbox store
        bridge (the reader task is busy dispatching the shutdown handler —
        a re-entrant store_save would deadlock). We route the payload
        through the bridge's store server so it lands at the same path the
        next run's warm-load reads from.
        """
        if not reply.HasField("restore_state"):
            return
        bridge = data.bridges.get(group)
        if bridge is None:
            _LOGGER.debug(
                "sandbox[%s]: shutdown reply carried restore_state but"
                " no bridge is registered; dropping",
                group,
            )
            return
        try:
            await bridge._handle_store_save(  # noqa: SLF001 — internal write path
                pb.StoreSave(key="core.restore_state", data=reply.restore_state)
            )
        except Exception:
            _LOGGER.exception(
                "Failed to persist restore_state snapshot for sandbox %s",
                group,
            )

    manager = SandboxManager(
        hass,
        on_channel_ready=_on_channel_ready,
        on_shutdown_reply=_on_shutdown_reply,
    )
    router = SandboxFlowRouter(hass, manager, data=data)
    data.manager = manager
    data.router = router

    hass.config_entries.router = router

    async def _on_stop(_event: Event) -> None:
        """Stop every sandbox process on HA shutdown.

        Phase 9: ask each sandbox to unload its entries and flush
        ``RestoreEntity`` state through the ``current_sandbox`` store
        bridge before pulling the plug. ``async_stop_all`` then handles SIGTERM
        / SIGKILL for any sandbox that didn't ack the graceful request
        within the grace.
        """
        hass.config_entries.router = None
        await manager.async_graceful_shutdown_all(timeout=manager.shutdown_grace)
        await manager.async_stop_all()
        data.channels.clear()
        data.bridges.clear()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _on_stop)

    return True
