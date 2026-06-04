"""Proxy :class:`ConfigFlow` that forwards every step to a sandbox runtime.

Behaviour:

1. The framework dispatches a flow step by name (``async_step_user``,
   ``async_step_reauth``, …) on the flow object. We catch *any* such
   call via ``__getattr__``.
2. On the **first** call we issue ``sandbox/flow_init`` with the
   integration domain plus the initial context/user input; the sandbox
   returns its own ``flow_id`` and the initial step's result.
3. **Subsequent** calls go out as ``sandbox/flow_step`` carrying the
   sandbox's ``flow_id`` and the user input from the framework.
4. On ``async_remove`` (framework cleanup) we fire
   ``sandbox/flow_abort`` so the sandbox tears its flow down too.
5. On the CREATE_ENTRY step we attach ``sandbox=<group>`` to the
   ``ConfigFlowResult`` so the framework's entry constructor sets
   :attr:`ConfigEntry.sandbox` before ``async_setup`` runs — that's
   where the router consults it.

The proxy never touches ``data_schema`` on the wire — schema-driven
validation happens *inside* the sandbox where the real schema lives. The
proxy treats the sandbox's reply as authoritative; a re-shown form (with
``errors`` set) is just another ``FORM`` result that the framework will
forward to the user as usual.
"""

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.data_entry_flow import FlowResultType

from ._proto import sandbox_pb2 as pb
from .channel import ChannelClosedError, ChannelRemoteError
from .messages import dict_to_struct, listvalue_to_list, struct_to_dict
from .schema_bridge import reconstruct_schema

if TYPE_CHECKING:
    from .manager import SandboxManager

_LOGGER = logging.getLogger(__name__)

# Holds fire-and-forget abort tasks alive long enough to complete; the
# framework's ``async_remove`` is synchronous so we can't await them inline.
_BACKGROUND_ABORTS: set = set()


class SandboxFlowProxy(ConfigFlow):
    """A flow handler that forwards each step to a sandbox runtime."""

    # Marker so other code (e.g. tests) can spot a proxy without isinstance
    # importing the sandbox package eagerly.
    _is_sandbox_proxy = True

    def __init__(
        self,
        *,
        sandbox_group: str,
        manager: SandboxManager,
        handler_key: str,
    ) -> None:
        """Initialise the proxy flow."""
        super().__init__()
        self._sandbox_group = sandbox_group
        self._manager = manager
        self._handler_key = handler_key
        self._sandbox_flow_id: str | None = None
        self._terminated: bool = False

    def __getattribute__(self, name: str) -> Any:
        """Catch every ``async_step_*`` access and forward to the sandbox.

        ConfigFlow's base class already defines several step methods (e.g.
        ``async_step_user``, ``async_step_ignore``, ``async_step_reauth*``),
        so we cannot rely on ``__getattr__`` — those names resolve in the
        normal MRO before ``__getattr__`` is consulted. ``__getattribute__``
        runs for every attribute access; we only re-wrap the
        ``async_step_*`` family.
        """
        if name.startswith("async_step_"):
            step_id = name[len("async_step_") :]
            forward = object.__getattribute__(self, "_forward_step")

            async def _step(
                user_input: dict[str, Any] | None = None,
            ) -> ConfigFlowResult:
                return await forward(step_id, user_input)

            _step.__name__ = name
            return _step
        return object.__getattribute__(self, name)

    async def _forward_step(
        self, step_id: str, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        if self._terminated:
            return self.async_abort(reason="sandbox_flow_terminated")

        sandbox = await self._manager.ensure_started(self._sandbox_group)
        channel = sandbox.channel
        if channel is None:  # pragma: no cover - manager guarantees this
            return self.async_abort(reason="sandbox_unavailable")

        try:
            if self._sandbox_flow_id is None:
                # First step — bootstrap the flow on the sandbox. The
                # framework's first call passes the initial data; for a
                # USER source this is None. Everything else (REAUTH,
                # DISCOVERY, …) gets its discovery payload here.
                request = pb.FlowInit(
                    handler=self._handler_key,
                    context=dict_to_struct(dict(self.context)),
                )
                if user_input is not None:
                    request.data.CopyFrom(dict_to_struct(user_input))
                result = await channel.call("sandbox/flow_init", request)
                self._sandbox_flow_id = (
                    result.flow_id if result.HasField("flow_id") else None
                )
            else:
                step = pb.FlowStep(flow_id=self._sandbox_flow_id)
                if user_input is not None:
                    step.user_input.CopyFrom(dict_to_struct(user_input))
                result = await channel.call("sandbox/flow_step", step)
        except ChannelClosedError:
            self._terminated = True
            _LOGGER.warning(
                "Sandbox %r channel closed mid-flow; aborting %s flow",
                self._sandbox_group,
                self._handler_key,
            )
            return self.async_abort(reason="sandbox_unavailable")
        except ChannelRemoteError as err:
            _LOGGER.warning(
                "Sandbox %r raised %s on %s step %s: %s",
                self._sandbox_group,
                err.error_type or "error",
                self._handler_key,
                step_id,
                err,
            )
            return self.async_abort(reason="sandbox_flow_error")

        await self._apply_remote_context(result)
        return self._adapt_result(result, step_id)

    async def _apply_remote_context(self, result: pb.FlowResult) -> None:
        """Mirror ``unique_id`` (and other context bits) onto our own flow.

        The sandbox's :meth:`ConfigFlow.async_set_unique_id` mutates the
        sandbox flow's ``context["unique_id"]``; the flow-runner surfaces
        it in the marshalled result. We pass it through
        :meth:`async_set_unique_id` so main's duplicate detection fires
        (it raises :class:`AbortFlow` for an in-progress collision,
        which the flow framework turns into an ABORT result).
        """
        if not result.HasField("context"):
            return
        remote = struct_to_dict(result.context)
        if "unique_id" not in remote:
            return
        unique_id = remote["unique_id"]
        if self.context.get("unique_id") == unique_id:
            return
        # ``async_set_unique_id`` raises ``AbortFlow("already_in_progress")``
        # if another flow for the same handler already has this unique
        # id; that's exactly the duplicate-rejection signal we want.
        await self.async_set_unique_id(unique_id)

    def _adapt_result(self, result: pb.FlowResult, step_id: str) -> ConfigFlowResult:
        """Translate a sandbox-side ``FlowResult`` message into a main-side one.

        The sandbox's ``flow_id`` and ``handler`` are replaced with main's
        view (so HA's frontend / FlowManager keep tracking the proxy
        flow), and CREATE_ENTRY data is tagged with the sandbox group so
        the setup interceptor knows where to route the entry.
        """
        result_type = FlowResultType(result.type)
        placeholders = (
            struct_to_dict(result.description_placeholders)
            if result.HasField("description_placeholders")
            else None
        )

        if result_type is FlowResultType.CREATE_ENTRY:
            entry_data = struct_to_dict(result.data)
            self._terminated = True
            create_result = self.async_create_entry(
                title=(
                    result.title
                    if result.HasField("title") and result.title
                    else self._handler_key
                ),
                data=entry_data,
                description=(
                    result.description if result.HasField("description") else None
                ),
                description_placeholders=placeholders,
            )
            # Tag the FlowResult so the framework's entry constructor in
            # ``ConfigEntriesFlowManager.async_finish_flow`` reads it into
            # ``ConfigEntry.sandbox`` — this lands the tag *before*
            # ``async_setup`` runs, where the router needs it.
            create_result["sandbox"] = self._sandbox_group
            return create_result

        if result_type is FlowResultType.ABORT:
            self._terminated = True
            return self.async_abort(
                reason=(
                    result.reason if result.HasField("reason") else "sandbox_aborted"
                ),
                description_placeholders=placeholders,
            )

        if result_type is FlowResultType.FORM:
            data_schema = reconstruct_schema(listvalue_to_list(result.data_schema))
            if data_schema is None and result.has_data_schema:
                _LOGGER.debug(
                    "Sandbox %r returned a FORM with an unserialisable"
                    " data_schema; rendering schema-less",
                    self._sandbox_group,
                )
            errors = (
                struct_to_dict(result.errors) if result.HasField("errors") else None
            )
            return self.async_show_form(
                step_id=result.step_id if result.HasField("step_id") else step_id,
                data_schema=data_schema,
                errors=errors or None,
                description_placeholders=placeholders,
                last_step=result.last_step if result.HasField("last_step") else None,
                preview=result.preview if result.HasField("preview") else None,
            )

        # Any other type (MENU, EXTERNAL_STEP, SHOW_PROGRESS, …) is
        # not supported; surface a noisy abort so a follow-up doesn't
        # silently drop the flow on the floor.
        self._terminated = True
        _LOGGER.warning(
            "Sandbox %r returned unsupported flow result type %s for %s;"
            " aborting (only FORM/CREATE_ENTRY/ABORT are supported)",
            self._sandbox_group,
            result_type,
            self._handler_key,
        )
        return self.async_abort(reason="sandbox_unsupported_result_type")

    def async_remove(self) -> None:
        """Tell the sandbox to drop its flow when the framework discards us."""
        if self._sandbox_flow_id is None or self._terminated:
            return
        sandbox = self._manager.get(self._sandbox_group)
        channel = sandbox.channel if sandbox is not None else None
        if channel is None:
            return
        # async_remove is a sync framework callback, but we're inside a
        # running HA loop — schedule the abort and move on.
        import asyncio  # noqa: PLC0415

        flow_id = self._sandbox_flow_id
        self._terminated = True
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # Called outside an event loop (teardown path); nothing useful
            # we can do — the sandbox's flow will GC when the process dies.
            return
        task = loop.create_task(
            _safe_abort(channel, flow_id, self._sandbox_group, self._handler_key)
        )
        _BACKGROUND_ABORTS.add(task)
        task.add_done_callback(_BACKGROUND_ABORTS.discard)


async def _safe_abort(channel: Any, flow_id: str, group: str, handler: str) -> None:
    """Fire ``flow_abort`` on the sandbox and swallow errors."""
    try:
        await channel.call("sandbox/flow_abort", pb.FlowAbort(flow_id=flow_id))
    except (ChannelClosedError, ChannelRemoteError) as err:
        _LOGGER.debug("Sandbox %r flow_abort for %s failed: %s", group, handler, err)


__all__ = ["SandboxFlowProxy"]
