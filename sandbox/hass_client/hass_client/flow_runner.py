"""Sandbox-side config flow runner.

Runs an integration's :class:`ConfigFlow` inside a dedicated
:class:`HomeAssistant` instance owned by the sandbox runtime. The
manager-side proxy :class:`ConfigFlow` calls these handlers across the
:class:`Channel`:

* ``sandbox/flow_init``  → ``(handler, source, context, data)``  → flow result
* ``sandbox/flow_step``  → ``(flow_id, user_input)``             → flow result
* ``sandbox/flow_abort`` → ``(flow_id)``                         → ``{}``

Flow results cross the wire as plain dicts. ``data_schema`` and the
``progress_task`` field are intentionally stripped — the schema lives on
the sandbox where validation happens, and the task is a runtime object
that can't be serialised. The docstring in ``_marshal_result`` is the
load-bearing note for how the schema is later marshalled.
"""

from collections.abc import Callable, Mapping
import contextlib
import ipaddress
import logging
from typing import Any, cast

from homeassistant import config_entries as ha_config_entries, loader
from homeassistant.config_entries import (
    ConfigEntriesFlowManager,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import BaseServiceInfo, FlowResultType, UnknownFlow
from homeassistant.helpers.discovery_flow import DiscoveryKey
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.hassio import HassioServiceInfo
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo
from homeassistant.helpers.service_info.usb import UsbServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from ._proto import sandbox_pb2 as pb
from .channel import Channel
from .messages import struct_to_dict
from .schema_bridge import serialize_schema

_LOGGER = logging.getLogger(__name__)


# Scalar optional-string fields copied verbatim from the integration's
# FlowResult onto the proto. Dynamic dicts (data / options / errors /
# description_placeholders / context) and data_schema get bespoke handling in
# ``_marshal_result``. MENU additionally carries menu_options / sort; the
# remaining result types (external-step / progress) carry no extra fields —
# the main-side proxy supports FORM / CREATE_ENTRY / ABORT / MENU and aborts
# cleanly on anything else.
_SCALAR_STRING_FIELDS = (
    "flow_id",
    "handler",
    "step_id",
    "reason",
    "title",
    "description",
)

# Dynamic dict fields → Struct fields of the same name on the proto.
_STRUCT_FIELDS = (
    "data",
    "options",
    "errors",
    "description_placeholders",
)


class _SandboxFlowManager(ConfigEntriesFlowManager):
    """ConfigEntriesFlowManager that doesn't add CREATE_ENTRY results.

    Main owns the canonical entry store; the sandbox just runs the flow
    and returns the result. The default ``async_finish_flow`` would
    create an entry inside the sandbox-private store and try to set the
    integration up locally — that's later work, not this layer's.
    """

    async def async_finish_flow(
        self, flow: Any, result: ConfigFlowResult
    ) -> ConfigFlowResult:
        if result["type"] is FlowResultType.CREATE_ENTRY:
            # Return the bare result so the channel marshaller sees the
            # full data/title/version payload; main builds the actual
            # ConfigEntry.
            self._set_pending_import_done(cast(ConfigFlow, flow))
            self._async_validate_next_flow(result)
            return result
        return await super().async_finish_flow(flow, result)


class FlowRunner:
    """Run config flows inside the sandbox process."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialise with a configured HomeAssistant instance."""
        self.hass = hass

    @classmethod
    async def create(cls, *, config_dir: str) -> FlowRunner:
        """Create a sandbox-private :class:`HomeAssistant` and wire it up."""
        hass = HomeAssistant(config_dir)
        hass.config.skip_pip = True
        hass.config.skip_pip_packages = []
        hass.config_entries = ha_config_entries.ConfigEntries(hass, {})
        # Swap in the sandbox-aware flow manager *after* ConfigEntries
        # has built its default one, so we inherit all the wiring.
        hass.config_entries.flow = _SandboxFlowManager(hass, hass.config_entries, {})
        loader.async_setup(hass)
        return cls(hass)

    def register(self, channel: Channel) -> None:
        """Register the ``sandbox/flow_*`` handlers on ``channel``."""
        channel.register("sandbox/flow_init", self._handle_flow_init)
        channel.register("sandbox/flow_step", self._handle_flow_step)
        channel.register("sandbox/flow_abort", self._handle_flow_abort)

    async def async_stop(self) -> None:
        """Tear down in-progress flows."""
        flow_manager = self.hass.config_entries.flow
        for progress in list(flow_manager.async_progress(include_uninitialized=True)):
            with contextlib.suppress(UnknownFlow):
                flow_manager.async_abort(progress["flow_id"])
        await self.hass.async_block_till_done()

    async def _handle_flow_init(self, msg: pb.FlowInit) -> pb.FlowResult:
        context = struct_to_dict(msg.context)
        data = struct_to_dict(msg.data) if msg.HasField("data") else None
        # Discovery-sourced flows carry their context/payload as JSON-safe
        # dicts (the proxy flattened the *ServiceInfo / DiscoveryKey objects);
        # rebuild the real types so async_step_<source> sees what it expects.
        context, data = _rehydrate_discovery(context, data)
        result = await self.hass.config_entries.flow.async_init(
            msg.handler, context=context, data=data
        )
        return _marshal_result(result, self.hass.config_entries.flow)

    async def _handle_flow_step(self, msg: pb.FlowStep) -> pb.FlowResult:
        user_input = (
            struct_to_dict(msg.user_input) if msg.HasField("user_input") else None
        )
        result = await self.hass.config_entries.flow.async_configure(
            msg.flow_id, user_input
        )
        return _marshal_result(result, self.hass.config_entries.flow)

    async def _handle_flow_abort(self, msg: pb.FlowAbort) -> pb.FlowAbortResult:
        with contextlib.suppress(UnknownFlow):
            # Idempotent — main may have already given up on the flow.
            self.hass.config_entries.flow.async_abort(msg.flow_id)
        return pb.FlowAbortResult()


def _marshal_result(
    result: Mapping[str, Any],
    flow_manager: ConfigEntriesFlowManager | None = None,
) -> pb.FlowResult:
    """Marshal a FlowResult into the typed ``FlowResult`` message.

    ``data_schema`` is rendered via :func:`serialize_schema` —
    the wire payload carries the same list-of-fields shape
    :func:`voluptuous_serialize.convert` produces, so the proxy on main
    can rebuild a usable :class:`vol.Schema`. ``flow.context`` (which
    carries ``unique_id`` once the integration calls
    :meth:`ConfigFlow.async_set_unique_id`) is pulled out of the live
    flow when the result type doesn't already include it.

    FORM / CREATE_ENTRY / ABORT / MENU fields are carried — the main-side proxy
    supports those four and aborts cleanly on anything else, so the
    external-step / progress extras (``subentries`` / ``url`` / …) are
    intentionally dropped.
    """
    out = pb.FlowResult(type=_flow_type_value(result["type"]))
    for key in _SCALAR_STRING_FIELDS:
        value = result.get(key)
        if value is not None:
            setattr(out, key, str(value))
    if result.get("version") is not None:
        out.version = int(result["version"])
    if result.get("minor_version") is not None:
        out.minor_version = int(result["minor_version"])
    if result.get("last_step") is not None:
        out.last_step = bool(result["last_step"])
    if result.get("preview") is not None:
        out.preview = str(result["preview"])
    menu_options = result.get("menu_options")
    if menu_options is not None:
        out.menu_options.extend(_marshal_menu_options(menu_options))
    if result.get("sort") is not None:
        out.sort = bool(result["sort"])
    for key in _STRUCT_FIELDS:
        value = result.get(key)
        if isinstance(value, Mapping):
            getattr(out, key).update(_to_json_safe(dict(value)))
    if result.get("data_schema") is not None:
        serialized = serialize_schema(result["data_schema"])
        if serialized is not None:
            out.data_schema.extend(serialized)
        else:
            # voluptuous_serialize couldn't render it; flag the gap so the
            # proxy still surfaces a (schema-less) form rather than abort.
            # Log the schema's repr at warning so the lossy fallback is
            # visible rather than silently swallowing a real form.
            _LOGGER.warning(
                "Could not serialize data_schema %r; main will render a"
                " schema-less form",
                result["data_schema"],
            )
            out.has_data_schema = True
    context_value = result.get("context")
    if isinstance(context_value, Mapping):
        out.context.update(_to_json_safe(dict(context_value)))
    elif flow_manager is not None:
        # FORM / SHOW_PROGRESS / EXTERNAL_STEP results don't include the
        # flow's context (only CREATE_ENTRY does). Look it up so the proxy
        # can mirror ``unique_id`` into its own ``self.context`` and let
        # main's duplicate detection fire.
        flow_id = result.get("flow_id")
        if isinstance(flow_id, str):
            try:
                partial = flow_manager.async_get(flow_id)
            except UnknownFlow:
                partial = None
            if partial is not None:
                ctx = partial.get("context")
                if isinstance(ctx, Mapping):
                    out.context.update(_to_json_safe(dict(ctx)))
    return out


def _build_zeroconf(data: dict[str, Any]) -> ZeroconfServiceInfo:
    """Rebuild a ZeroconfServiceInfo from its JSON-flattened dict."""
    return ZeroconfServiceInfo(
        ip_address=ipaddress.ip_address(data["ip_address"]),
        ip_addresses=[ipaddress.ip_address(addr) for addr in data["ip_addresses"]],
        port=data.get("port"),
        hostname=data["hostname"],
        type=data["type"],
        name=data["name"],
        properties=data["properties"],
    )


def _build_ssdp(data: dict[str, Any]) -> SsdpServiceInfo:
    """Rebuild an SsdpServiceInfo, restoring its set-typed fields."""
    return SsdpServiceInfo(
        ssdp_usn=data["ssdp_usn"],
        ssdp_st=data["ssdp_st"],
        upnp=data["upnp"],
        ssdp_location=data.get("ssdp_location"),
        ssdp_nt=data.get("ssdp_nt"),
        ssdp_udn=data.get("ssdp_udn"),
        ssdp_ext=data.get("ssdp_ext"),
        ssdp_server=data.get("ssdp_server"),
        ssdp_headers=data.get("ssdp_headers", {}),
        ssdp_all_locations=set(data.get("ssdp_all_locations", [])),
        x_homeassistant_matching_domains=set(
            data.get("x_homeassistant_matching_domains", [])
        ),
    )


# Discovery source -> builder that reconstructs the BaseServiceInfo the real
# ``async_step_<source>`` expects from the JSON-flattened wire dict. Sources
# whose info type is a plain flat dataclass take ``Class(**data)``; zeroconf /
# ssdp need field coercion. ``homekit`` reuses ZeroconfServiceInfo. Bluetooth is
# intentionally absent (its info is an external non-trivially-rebuildable type);
# an unmapped source leaves ``data`` as a dict and the integration step — not
# the bridge — decides what to do, with the proxy aborting cleanly if it raises.
_DISCOVERY_INFO_BUILDERS: dict[str, Callable[[dict[str, Any]], BaseServiceInfo]] = {
    "zeroconf": _build_zeroconf,
    "homekit": _build_zeroconf,
    "ssdp": _build_ssdp,
    "dhcp": lambda data: DhcpServiceInfo(**data),
    "usb": lambda data: UsbServiceInfo(**data),
    "hassio": lambda data: HassioServiceInfo(**data),
    "mqtt": lambda data: MqttServiceInfo(**data),
}


def _rehydrate_discovery(
    context: dict[str, Any], data: Any
) -> tuple[dict[str, Any], Any]:
    """Rebuild discovery objects flattened by the proxy for the wire.

    Restores ``context["discovery_key"]`` to a :class:`DiscoveryKey` and the
    first-step ``data`` to the source's :class:`BaseServiceInfo`. Reconstruction
    failures degrade to the plain dict rather than crash — the proxy's broadened
    abort is the outer backstop.
    """
    discovery_key = context.get("discovery_key")
    if isinstance(discovery_key, Mapping):
        context = {
            **context,
            "discovery_key": DiscoveryKey.from_json_dict(dict(discovery_key)),
        }
    builder = _DISCOVERY_INFO_BUILDERS.get(context.get("source", ""))
    if builder is not None and isinstance(data, Mapping):
        try:
            data = builder(dict(data))
        except (TypeError, ValueError, KeyError) as err:
            _LOGGER.warning(
                "Could not rebuild %s discovery info (%s); passing the raw dict",
                context.get("source"),
                err,
            )
    return context, data


def _marshal_menu_options(menu_options: Any) -> list[Any]:
    """Render MENU ``menu_options`` (list[str] or dict[str,str]) as a wire list.

    A dict maps step-id → label; it crosses as a list of ``[id, label]`` pairs
    so order and labels survive the round-trip. A plain list crosses as a list
    of step-id strings. The proxy on main rebuilds the original shape.
    """
    if isinstance(menu_options, Mapping):
        return [[str(key), str(label)] for key, label in menu_options.items()]
    return [str(option) for option in menu_options]


def _flow_type_value(value: Any) -> str:
    """Return the string value of a FlowResult ``type`` (enum or string)."""
    if isinstance(value, FlowResultType):
        return value.value
    return str(value)


def _to_json_safe(value: Any) -> Any:
    """Recursively coerce a value into JSON-safe primitives."""
    if isinstance(value, Mapping):
        return {str(k): _to_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_to_json_safe(v) for v in value]
    if isinstance(value, FlowResultType):
        return value.value
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    # Generic enum-ish: fall through to .value if available, otherwise str().
    enum_value = getattr(value, "value", None)
    if enum_value is not None and isinstance(enum_value, (str, int, float, bool)):
        return enum_value
    return str(value)


__all__ = ["FlowRunner"]
