"""Proxy :class:`ConfigFlow` that forwards every step to a sandbox runtime."""

from collections.abc import Mapping
import dataclasses
from ipaddress import IPv4Address, IPv6Address
import logging
from typing import TYPE_CHECKING, Any, override

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
)
from homeassistant.data_entry_flow import FlowResultType

from ._proto import sandbox_pb2 as pb
from .channel import ChannelClosedError, ChannelRemoteError
from .const import DATA_SANDBOX
from .messages import (
    MSG_FLOW_ABORT,
    MSG_FLOW_INIT,
    MSG_FLOW_STEP,
    decode_json,
    decode_json_dict,
    encode_json,
    entry_to_setup_proto,
)
from .schema_bridge import reconstruct_schema

if TYPE_CHECKING:
    from .manager import SandboxManager

_LOGGER = logging.getLogger(__name__)

# Holds fire-and-forget abort tasks alive long enough to complete; the
# framework's ``async_remove`` is synchronous so we can't await them inline.
_BACKGROUND_ABORTS: set = set()


def _to_jsonable(value: Any) -> Any:
    """Coerce a flow ``context`` / first-step payload into plain JSON data."""
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


class _SandboxFlowProxyMixin:
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
        subentry_type: str | None = None,
    ) -> None:
        """Initialise the proxy flow."""
        super().__init__()
        self._sandbox_group = sandbox_group
        self._manager = manager
        self._handler_key = handler_key
        self._remote_subentry_type = subentry_type
        self._sandbox_flow_id: str | None = None
        self._terminated: bool = False
        # Translate menu dispatch into navigation on the existing worker flow.
        self._awaiting_menu_selection: bool = False

    @property
    def sandbox_group(self) -> str:
        """The sandbox group this in-progress flow forwards to."""
        return self._sandbox_group

    @override
    def __getattribute__(self, name: str) -> Any:
        """Catch every ``async_step_*`` access and forward to the sandbox."""
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
                # Discovery and reauth flows need their initial payload on the first step.
                request = pb.FlowInit(
                    handler=self._handler_key,
                    context=encode_json(_to_jsonable(dict(self.context))),
                )
                if self._remote_subentry_type is not None:
                    request.subentry_type = self._remote_subentry_type
                if user_input is not None:
                    request.data = encode_json(_to_jsonable(user_input))
                # Seed the main-owned entry so worker flows can resolve it.
                if (
                    entry_id := (
                        self.handler[0]
                        if self._remote_subentry_type is not None
                        else self.context.get("entry_id")
                    )
                ) is not None and (
                    entry := self.hass.config_entries.async_get_entry(entry_id)
                ) is not None:
                    sandbox_data = self.hass.data.get(DATA_SANDBOX)
                    if (
                        sandbox_data is not None
                        and (bridge := sandbox_data.bridges.get(self._sandbox_group))
                        is not None
                    ):
                        await bridge.entry_sync.flush(entry.entry_id)
                        bridge.entry_sync.track(entry)
                    request.entry.CopyFrom(entry_to_setup_proto(entry))
                result = await channel.call(MSG_FLOW_INIT, request)
                self._sandbox_flow_id = (
                    result.flow_id if result.HasField("flow_id") else None
                )
            else:
                step = pb.FlowStep(flow_id=self._sandbox_flow_id)
                if self._awaiting_menu_selection:
                    # Menu choices continue the current step instead of starting a new one.
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
        """Mirror ``unique_id`` (and other context bits) onto our own flow."""
        if self._remote_subentry_type is not None or not result.HasField("context"):
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
        """Translate a sandbox-side ``FlowResult`` message into a main-side one."""
        result_type = FlowResultType(result.type)
        placeholders = (
            decode_json_dict(result.description_placeholders)
            if result.HasField("description_placeholders")
            else None
        )

        if result_type is FlowResultType.CREATE_ENTRY:
            entry_data = decode_json_dict(result.data)
            if self._remote_subentry_type is not None:
                self._terminated = True
                return self.async_create_entry(
                    title=result.title,
                    data=entry_data,
                    unique_id=result.unique_id
                    if result.HasField("unique_id")
                    else None,
                )
            options = (
                decode_json_dict(result.options) if result.HasField("options") else None
            )
            self._terminated = True
            # Preserve the integration schema version to avoid a spurious migration.
            if result.HasField("version"):
                self.VERSION = result.version
            if result.HasField("minor_version"):
                self.MINOR_VERSION = result.minor_version
            create_result = self.async_create_entry(
                title=(result.title if result.HasField("title") else self._handler_key),
                data=entry_data,
                description=(
                    result.description if result.HasField("description") else None
                ),
                description_placeholders=placeholders,
                options=options,
                subentries=decode_json(result.subentries) or (),
            )
            # Set placement before config-entry setup consults the router.
            create_result["sandbox"] = self._sandbox_group
            return create_result

        if result_type is FlowResultType.ABORT:
            self._terminated = True
            return self.async_abort(
                reason=(
                    result.reason if result.HasField("reason") else "sandbox_aborted"
                ),
                translation_domain=result.translation_domain
                if result.HasField("translation_domain")
                else None,
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

        # Leave the flow abortable so unsupported results cannot strand its unique ID.
        _LOGGER.warning(
            "Sandbox %r returned unsupported flow result type %s for %s;"
            " aborting (only FORM/CREATE_ENTRY/ABORT/MENU are supported)",
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


class SandboxFlowProxy(_SandboxFlowProxyMixin, ConfigFlow):
    """Forward a config-entry flow to its worker."""


class SandboxSubentryFlowProxy(_SandboxFlowProxyMixin, ConfigSubentryFlow):
    """Forward a subentry flow while main owns the resulting subentry."""


def _reconstruct_menu_options(items: list[Any]) -> list[str] | dict[str, str]:
    """Rebuild MENU ``menu_options`` from the wire list."""
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
