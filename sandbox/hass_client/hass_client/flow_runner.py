"""Sandbox-side config flow runner."""

import asyncio
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
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.data_entry_flow import BaseServiceInfo, FlowResultType, UnknownFlow
from homeassistant.helpers import (
    area_registry as ar,
    category_registry as cr,
    device_registry as dr,
    entity,
    entity_registry as er,
    floor_registry as fr,
    frame,
    issue_registry as ir,
    label_registry as lr,
    translation,
)
from homeassistant.helpers.discovery_flow import DiscoveryKey
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.hassio import HassioServiceInfo
from homeassistant.helpers.service_info.mqtt import MqttServiceInfo
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo
from homeassistant.helpers.service_info.usb import UsbServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from ._proto import sandbox_pb2 as pb
from .channel import Channel
from .entry_runner import _entry_from_proto
from .entry_sync import EntrySync
from .messages import (
    MSG_FLOW_ABORT,
    MSG_FLOW_INIT,
    MSG_FLOW_STEP,
    decode_json_dict,
    encode_json,
)
from .schema_bridge import serialize_schema

_LOGGER = logging.getLogger(__name__)


# Copy scalar flow metadata; structured fields require separate serialization.
_SCALAR_STRING_FIELDS = (
    "flow_id",
    "handler",
    "step_id",
    "reason",
    "translation_domain",
    "title",
    "description",
)

# Dynamic dict fields → JSON-bytes fields of the same name on the proto.
_DYNAMIC_DICT_FIELDS = (
    "data",
    "options",
    "errors",
    "description_placeholders",
)


class _SandboxFlowManager(ConfigEntriesFlowManager):
    """ConfigEntriesFlowManager that doesn't add CREATE_ENTRY results."""

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


class _SandboxSubentryFlowManager(ha_config_entries.ConfigSubentryFlowManager):
    """Leave new subentry creation to main, which assigns the stable ID."""

    async def async_finish_flow(self, flow: Any, result: Any) -> Any:
        return result


class FlowRunner:
    """Run config flows inside the sandbox process."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialise with a configured HomeAssistant instance."""
        self.hass = hass
        self.entry_sync: EntrySync | None = None
        self._subentry_flows: set[str] = set()

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
        hass.config_entries.subentries = _SandboxSubentryFlowManager(hass)
        loader.async_setup(hass)
        # Load registries before enabling remote storage so their initial data stays local.
        entity.async_setup(hass)
        frame.async_setup(hass)
        translation.async_setup(hass)
        dr.async_setup(hass)
        await asyncio.gather(
            ar.async_load(hass),
            cr.async_load(hass),
            dr.async_load(hass),
            er.async_load(hass),
            fr.async_load(hass),
            ir.async_load(hass),
            lr.async_load(hass),
        )
        await hass.config_entries.async_initialize()
        return cls(hass)

    def register(self, channel: Channel) -> None:
        """Register the ``sandbox/flow_*`` handlers on ``channel``."""
        channel.register(MSG_FLOW_INIT, self._handle_flow_init)
        channel.register(MSG_FLOW_STEP, self._handle_flow_step)
        channel.register(MSG_FLOW_ABORT, self._handle_flow_abort)

    async def async_stop(self) -> None:
        """Tear down in-progress flows and stop the private hass."""
        for flow_manager in (
            self.hass.config_entries.flow,
            self.hass.config_entries.subentries,
        ):
            for progress in list(
                flow_manager.async_progress(include_uninitialized=True)
            ):
                with contextlib.suppress(UnknownFlow):
                    flow_manager.async_abort(progress["flow_id"])
        await self.hass.async_block_till_done()
        if self.hass.state is not CoreState.stopped:
            await self.hass.async_stop(force=True)

    async def _handle_flow_init(self, msg: pb.FlowInit) -> pb.FlowResult:
        context = decode_json_dict(msg.context)
        data = decode_json_dict(msg.data) if msg.HasField("data") else None
        # Discovery-sourced flows carry their context/payload as JSON-safe
        # dicts (the proxy flattened the *ServiceInfo / DiscoveryKey objects);
        # rebuild the real types so async_step_<source> sees what it expects.
        context, data = _rehydrate_discovery(context, data)
        # Seed the main-owned entry before the worker flow looks it up.
        if msg.HasField("entry"):
            self._ensure_flow_entry(msg.entry)
        if msg.HasField("subentry_type"):
            manager = self.hass.config_entries.subentries
            result = await manager.async_init(
                (msg.entry.entry_id, msg.subentry_type), context=context, data=data
            )
            if result["type"] not in (
                FlowResultType.CREATE_ENTRY,
                FlowResultType.ABORT,
            ):
                self._subentry_flows.add(result["flow_id"])
        else:
            manager = self.hass.config_entries.flow
            result = await manager.async_init(msg.handler, context=context, data=data)
        if self.entry_sync is not None:
            await self.entry_sync.flush()
        return _marshal_result(result, manager)

    def _ensure_flow_entry(self, entry_msg: pb.EntrySetup) -> None:
        """Seed the private config_entries with the flow's target entry."""
        config_entries = self.hass.config_entries
        if config_entries.async_get_entry(entry_msg.entry_id) is not None:
            return
        entry = _entry_from_proto(entry_msg)
        config_entries._entries[entry.entry_id] = entry  # noqa: SLF001
        if self.entry_sync is not None:
            self.entry_sync.track(entry)

    async def _handle_flow_step(self, msg: pb.FlowStep) -> pb.FlowResult:
        user_input = (
            decode_json_dict(msg.user_input) if msg.HasField("user_input") else None
        )
        manager = (
            self.hass.config_entries.subentries
            if msg.flow_id in self._subentry_flows
            else self.hass.config_entries.flow
        )
        result = await manager.async_configure(msg.flow_id, user_input)
        if result["type"] in (FlowResultType.CREATE_ENTRY, FlowResultType.ABORT):
            self._subentry_flows.discard(msg.flow_id)
        if self.entry_sync is not None:
            await self.entry_sync.flush()
        return _marshal_result(result, manager)

    async def _handle_flow_abort(self, msg: pb.FlowAbort) -> pb.FlowAbortResult:
        with contextlib.suppress(UnknownFlow):
            # Idempotent — main may have already given up on the flow.
            manager = (
                self.hass.config_entries.subentries
                if msg.flow_id in self._subentry_flows
                else self.hass.config_entries.flow
            )
            manager.async_abort(msg.flow_id)
        self._subentry_flows.discard(msg.flow_id)
        return pb.FlowAbortResult()


def _marshal_result(
    result: Mapping[str, Any],
    flow_manager: ConfigEntriesFlowManager | None = None,
) -> pb.FlowResult:
    """Marshal a FlowResult into the typed ``FlowResult`` message."""
    out = pb.FlowResult(type=_flow_type_value(result["type"]))
    for key in _SCALAR_STRING_FIELDS:
        value = result.get(key)
        if value is not None:
            setattr(out, key, str(value))
    if "subentries" in result:
        out.subentries = encode_json(list(result["subentries"]))
    if result.get("unique_id") is not None:
        out.unique_id = result["unique_id"]
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
        out.menu_options = encode_json(_marshal_menu_options(menu_options))
    if result.get("sort") is not None:
        out.sort = bool(result["sort"])
    for key in _DYNAMIC_DICT_FIELDS:
        value = result.get(key)
        if isinstance(value, Mapping):
            setattr(out, key, encode_json(dict(value)))
    if result.get("data_schema") is not None:
        serialized = serialize_schema(result["data_schema"])
        if serialized is not None:
            out.data_schema = encode_json(serialized)
        else:
            # Log lossy schemas so an unsupported form does not fail silently.
            _LOGGER.warning(
                "Could not serialize data_schema %r; main will render a"
                " schema-less form",
                result["data_schema"],
            )
            out.has_data_schema = True
    context_value = result.get("context")
    if isinstance(context_value, Mapping):
        out.context = encode_json(dict(context_value))
    elif flow_manager is not None:
        # Read the active flow context because nonterminal results omit the unique ID.
        flow_id = result.get("flow_id")
        if isinstance(flow_id, str):
            try:
                partial = flow_manager.async_get(flow_id)
            except UnknownFlow:
                partial = None
            if partial is not None:
                ctx = partial.get("context")
                if isinstance(ctx, Mapping):
                    out.context = encode_json(dict(ctx))
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


# Reconstruct discovery types whose integration steps require typed attributes.
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
    """Rebuild discovery objects flattened by the proxy for the wire."""
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
    """Render MENU ``menu_options`` (list[str] or dict[str,str]) as a wire list."""
    if isinstance(menu_options, Mapping):
        return [[str(key), str(label)] for key, label in menu_options.items()]
    return [str(option) for option in menu_options]


def _flow_type_value(value: Any) -> str:
    """Return the string value of a FlowResult ``type`` (enum or string)."""
    if isinstance(value, FlowResultType):
        return value.value
    return str(value)


__all__ = ["FlowRunner"]
