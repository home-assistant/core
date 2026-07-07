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

from collections.abc import Mapping
import dataclasses
from ipaddress import IPv4Address, IPv6Address
import logging
from typing import TYPE_CHECKING, Any, override

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.data_entry_flow import FlowResultType

from ._proto import sandbox_pb2 as pb
from .channel import ChannelClosedError, ChannelRemoteError
from .messages import (
    MSG_FLOW_ABORT,
    MSG_FLOW_INIT,
    MSG_FLOW_STEP,
    decode_json,
    decode_json_dict,
    encode_json,
)
from .schema_bridge import reconstruct_schema

if TYPE_CHECKING:
    from .manager import SandboxManager

_LOGGER = logging.getLogger(__name__)

# Holds fire-and-forget abort tasks alive long enough to complete; the
# framework's ``async_remove`` is synchronous so we can't await them inline.
_BACKGROUND_ABORTS: set = set()


def _to_jsonable(value: Any) -> Any:
    """Coerce a flow ``context`` / first-step payload into plain JSON data.

    Discovery flows carry objects with no generic JSON shape: the
    ``*ServiceInfo`` dataclass as the first-step ``user_input`` (with
    ``IPv4Address`` fields, sets, …) and a :class:`DiscoveryKey` dataclass in
    ``context``. Walk the structure into plain JSON primitives, flattening
    dataclasses to per-field dicts, so the sandbox side rebuilds the real
    objects from the same field names (see ``flow_runner._rehydrate_discovery``).
    """
    if isinstance(value, Mapping):
        return {str(key): _to_jsonable(val) for key, val in value.items()}
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _to_jsonable(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (str, int, float)):
        return value
    if isinstance(value, (IPv4Address, IPv6Address)):
        return str(value)
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    # Last-resort backstop for an exotic type: fall through to ``.value`` if it
    # looks enum-ish, else ``str()`` — never let an unmappable object crash the
    # marshal (the broadened ``except`` in ``_forward_step`` is the next net).
    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, (str, int, float, bool)):
        return enum_value
    return str(value)


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
        # Set when the last sandbox result was a MENU: the framework then
        # dispatches ``async_step_<chosen>`` for the selected option, which we
        # must forward as the sandbox flow's ``{"next_step_id": <chosen>}``
        # menu navigation rather than a fresh step.
        self._awaiting_menu_selection: bool = False

    @property
    def sandbox_group(self) -> str:
        """The sandbox group this in-progress flow forwards to.

        Read by the translation provider to resolve a brand-new custom
        integration's group before any ``ConfigEntry`` exists.
        """
        return self._sandbox_group

    @override
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
                    context=encode_json(_to_jsonable(dict(self.context))),
                )
                if user_input is not None:
                    request.data = encode_json(_to_jsonable(user_input))
                result = await channel.call(MSG_FLOW_INIT, request)
                self._sandbox_flow_id = (
                    result.flow_id if result.HasField("flow_id") else None
                )
            else:
                step = pb.FlowStep(flow_id=self._sandbox_flow_id)
                if self._awaiting_menu_selection:
                    # The framework dispatched ``async_step_<chosen>`` for the
                    # menu option the user picked; the sandbox flow expects that
                    # as a ``{"next_step_id": <chosen>}`` selection on its menu
                    # step, not a fresh step call.
                    self._awaiting_menu_selection = False
                    step.user_input = encode_json({"next_step_id": step_id})
                elif user_input is not None:
                    step.user_input = encode_json(user_input)
                result = await channel.call(MSG_FLOW_STEP, step)
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
        except (TypeError, ValueError) as err:
            # Backstop: an unmapped payload type slipped past ``_to_jsonable``
            # and ``encode_json`` rejected it (orjson raises a TypeError
            # subclass). Abort cleanly rather than let the marshalling
            # exception crash the flow unhandled.
            _LOGGER.warning(
                "Sandbox %r could not marshal %s step %s payload: %s; aborting",
                self._sandbox_group,
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
        remote = decode_json_dict(result.context)
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
            decode_json_dict(result.description_placeholders)
            if result.HasField("description_placeholders")
            else None
        )

        if result_type is FlowResultType.CREATE_ENTRY:
            entry_data = decode_json_dict(result.data)
            options = (
                decode_json_dict(result.options) if result.HasField("options") else None
            )
            self._terminated = True
            # ``async_create_entry`` stamps the created result's
            # ``version``/``minor_version`` from ``self.VERSION``/
            # ``self.MINOR_VERSION`` (read off the instance, not the class —
            # see ``ConfigFlow.async_create_entry``). Override the proxy
            # instance's values with the sandbox flow's so the entry carries
            # the integration's real schema version; otherwise the proxy's
            # default ``VERSION=1`` triggers a spurious migration on next setup.
            if result.HasField("version"):
                self.VERSION = result.version
            if result.HasField("minor_version"):
                self.MINOR_VERSION = result.minor_version
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
                options=options,
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
            data_schema = reconstruct_schema(decode_json(result.data_schema))
            if data_schema is None and result.has_data_schema:
                _LOGGER.debug(
                    "Sandbox %r returned a FORM with an unserialisable"
                    " data_schema; rendering schema-less",
                    self._sandbox_group,
                )
            errors = (
                decode_json_dict(result.errors) if result.HasField("errors") else None
            )
            return self.async_show_form(
                step_id=result.step_id if result.HasField("step_id") else step_id,
                data_schema=data_schema,
                errors=errors or None,
                description_placeholders=placeholders,
                last_step=result.last_step if result.HasField("last_step") else None,
                preview=result.preview if result.HasField("preview") else None,
            )

        if result_type is FlowResultType.MENU:
            menu_options = _reconstruct_menu_options(
                decode_json(result.menu_options) or []
            )
            # The framework will dispatch ``async_step_<chosen>`` for the
            # option the user picks; mark that the next forwarded step is a
            # menu navigation choice (see ``_forward_step``).
            self._awaiting_menu_selection = True
            return self.async_show_menu(
                step_id=result.step_id if result.HasField("step_id") else step_id,
                menu_options=menu_options,
                sort=result.sort if result.HasField("sort") else False,
                description_placeholders=placeholders,
            )

        # Remaining types (EXTERNAL_STEP, SHOW_PROGRESS, …) are not supported;
        # surface a noisy abort. We deliberately do NOT set ``_terminated`` here:
        # the sandbox-side flow is still in progress (it returned a non-terminal
        # result), so ``async_remove`` must still fire ``flow_abort`` to reap it —
        # otherwise a flow that set a ``unique_id`` wedges retries on
        # ``already_in_progress`` until the sandbox restarts.
        _LOGGER.warning(
            "Sandbox %r returned unsupported flow result type %s for %s;"
            " aborting (only FORM/CREATE_ENTRY/ABORT/MENU are supported)",
            self._sandbox_group,
            result_type,
            self._handler_key,
        )
        return self.async_abort(reason="sandbox_unsupported_result_type")

    @override
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


def _reconstruct_menu_options(items: list[Any]) -> list[str] | dict[str, str]:
    """Rebuild MENU ``menu_options`` from the wire list.

    A dict (id → label) form crossed as a list of ``[id, label]`` pairs; a list
    form crossed as a list of step-id strings. Mirror :func:`_marshal_menu_options`
    on the sandbox side.
    """
    if items and all(isinstance(item, list) and len(item) == 2 for item in items):
        return {str(item[0]): str(item[1]) for item in items}
    return [str(item) for item in items]


async def _safe_abort(channel: Any, flow_id: str, group: str, handler: str) -> None:
    """Fire ``flow_abort`` on the sandbox and swallow errors."""
    try:
        await channel.call(MSG_FLOW_ABORT, pb.FlowAbort(flow_id=flow_id))
    except (ChannelClosedError, ChannelRemoteError) as err:
        _LOGGER.debug("Sandbox %r flow_abort for %s failed: %s", group, handler, err)


__all__ = ["SandboxFlowProxy"]
