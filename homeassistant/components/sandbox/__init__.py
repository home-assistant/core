"""Sandbox — run integrations in isolated subprocesses.

The integration owns three runtime objects, all hung off
:class:`SandboxData`:

* :class:`SandboxManager` — supervises one subprocess per sandbox group
  ("main", "built-in", "custom"), lazily spawning them on first need.
* :class:`SandboxFlowRouter` — installed as
  ``hass.config_entries.router``. Diverts new config flows to
  sandbox runtimes and routes ``async_setup_entry`` for tagged entries.
* :class:`SandboxBridge` (one per running sandbox) — owns the entity-side
  protocol: receives ``register_entity`` + ``state_changed`` pushes from
  the sandbox, instantiates proxy entities, and forwards entity service
  calls back via the shared ``sandbox/call_service`` channel.
"""

from dataclasses import dataclass, field
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.translation import (
    async_register_sandbox_translation_provider,
)
from homeassistant.helpers.typing import ConfigType

from ._proto import sandbox_pb2 as pb
from .bridge import SandboxBridge, async_create_bridge
from .channel import Channel
from .const import DATA_SANDBOX, DOMAIN
from .manager import SandboxManager
from .router import SandboxFlowRouter
from .translation import SandboxTranslationProvider

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


@dataclass
class SandboxData:
    """Global Sandbox runtime data."""

    manager: SandboxManager | None = None
    router: SandboxFlowRouter | None = None
    channels: dict[str, Channel] = field(default_factory=dict)
    bridges: dict[str, SandboxBridge] = field(default_factory=dict)
    # A bridge displaced by a restart, held until the fresh process goes
    # ready so its proxies + platform slots can be torn down right before
    # the replacement re-registers the same entries (keyed by group).
    pending_teardown: dict[str, SandboxBridge] = field(default_factory=dict)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Sandbox integration."""
    data = SandboxData()
    hass.data[DATA_SANDBOX] = data

    def _on_channel_ready(group: str, channel: Channel) -> None:
        # A sandbox restart hands us a fresh channel; the previous bridge
        # owned the dead one. Install the new bridge now (its handlers must
        # be live before the channel reader starts) but defer tearing the
        # old one down — its proxies + EntityComponent platform slots are
        # released in ``_on_ready`` right before the fresh process
        # re-registers, so the entities stay visible (Phase 2 marks them
        # unavailable) across the restart gap instead of vanishing.
        old_bridge = data.bridges.get(group)
        data.channels[group] = channel
        data.bridges[group] = async_create_bridge(hass, group=group, channel=channel)
        if old_bridge is None:
            return
        # A second crash before the first respawn went ready would orphan
        # the earlier pending bridge — tear it down now so neither leaks.
        previous = data.pending_teardown.get(group)
        if previous is not None and previous is not old_bridge:
            hass.async_create_task(previous.async_teardown())
        data.pending_teardown[group] = old_bridge

    def _on_ready(group: str) -> None:
        # The fresh process is up and can answer ``entry_setup``. Tear down
        # the displaced bridge and re-drive setup for the group's entries so
        # the new bridge repopulates. Capturing the loaded entries
        # synchronously here is what keeps a *first* start (entries not yet
        # loaded) from being mistaken for a respawn and double-setting-up.
        old_bridge = data.pending_teardown.pop(group, None)
        loaded = [
            entry.entry_id
            for entry in hass.config_entries.async_entries()
            if entry.sandbox == group and entry.state is ConfigEntryState.LOADED
        ]
        if old_bridge is None and not loaded:
            return
        hass.async_create_task(_async_recover_group(old_bridge, loaded))

    async def _async_recover_group(
        old_bridge: SandboxBridge | None, loaded_entry_ids: list[str]
    ) -> None:
        # Teardown must complete before the reload's setup re-registers the
        # same entry — otherwise ``async_register_remote_platform`` trips the
        # "already been setup!" guard on the still-registered old platform.
        if old_bridge is not None:
            await old_bridge.async_teardown()
        for entry_id in loaded_entry_ids:
            hass.config_entries.async_schedule_reload(entry_id)

    async def _on_shutdown_reply(group: str, reply: Any) -> None:
        """Persist the sandbox's restore-state snapshot.

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
        on_ready=_on_ready,
        on_shutdown_reply=_on_shutdown_reply,
    )
    router = SandboxFlowRouter(hass, manager, data=data)
    data.manager = manager
    data.router = router

    hass.config_entries.router = router

    # Feed sandboxed integrations' frontend translations into core's cache.
    # Built-in domains read main's own disk; only customs pull over RPC.
    translation_provider = SandboxTranslationProvider(hass, data)
    unregister_translation_provider = async_register_sandbox_translation_provider(
        hass, translation_provider.async_get_translations
    )

    async def _on_stop(_event: Event) -> None:
        """Stop every sandbox process on HA shutdown.

        Ask each sandbox to unload its entries and flush
        ``RestoreEntity`` state through the ``current_sandbox`` store
        bridge before pulling the plug. ``async_stop_all`` then handles SIGTERM
        / SIGKILL for any sandbox that didn't ack the graceful request
        within the grace.
        """
        hass.config_entries.router = None
        unregister_translation_provider()
        await manager.async_graceful_shutdown_all(timeout=manager.shutdown_grace)
        await manager.async_stop_all()
        data.channels.clear()
        data.bridges.clear()
        data.pending_teardown.clear()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _on_stop)

    return True
