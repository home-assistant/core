"""Service-forwarding helpers for mirrored sandbox services.

Builds the main-side forwarder installed by ``sandbox/register_service``
(every call ships back over the bridge's shared ``sandbox/call_service``
channel) and translates sandbox-side exceptions back into the types
main-side callers expect. The bridge exposes ``remember_context`` /
``async_raw_call_service`` as the declared interface this module drives.
"""

from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.core import ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError

from .channel import ChannelRemoteError
from .messages import decode_json_dict

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .bridge import SandboxBridge


def parse_supports_response(value: str) -> SupportsResponse:
    """Coerce the wire ``supports_response`` field into the enum."""
    try:
        return SupportsResponse(value.lower())
    except ValueError:
        return SupportsResponse.NONE


def build_service_forwarder(
    bridge: SandboxBridge,
    domain: str,
    service: str,
    supports_response: SupportsResponse,
) -> Callable[[ServiceCall], Coroutine[Any, Any, Any]]:
    """Return a callable suitable for :meth:`ServiceRegistry.async_register`.

    The forwarder rebuilds the original service-call payload and ships it
    back over the sandbox's shared ``sandbox/call_service`` channel.
    Schema validation already ran on the way in (main's registry runs
    ``schema=None`` because the sandbox owns the schema); the sandbox
    runs the real handler against its own entities and registry.
    """

    async def _forward(call: ServiceCall) -> Any:
        # Remember the real (main-issued) Context so the sandbox echoing this
        # id back on a derived state/event restores it verbatim.
        bridge.remember_context(call.context)
        response = await bridge.async_raw_call_service(
            domain=domain,
            service=service,
            target=_target_from_call(call),
            service_data=dict(call.data),
            context_id=call.context.id if call.context is not None else None,
            return_response=call.return_response,
        )
        if supports_response is SupportsResponse.NONE:
            return None
        if response.HasField("response"):
            return decode_json_dict(response.response.data)
        return None

    return _forward


def _target_from_call(call: ServiceCall) -> dict[str, Any]:
    """Extract a ``target`` dict from the (already-validated) service call."""
    target: dict[str, Any] = {}
    if not call.data:
        return target
    for key in ("entity_id", "area_id", "device_id", "floor_id", "label_id"):
        value = call.data.get(key)
        if value is None:
            continue
        target[key] = list(value) if isinstance(value, (list, tuple, set)) else value
    return target


def _rebuild_invalid(data: Mapping[str, Any]) -> vol.Invalid:
    """Rebuild a single :class:`vol.Invalid` from its serialized payload."""
    path = data.get("path") or None
    return vol.Invalid(data.get("msg", ""), path=path)


def translate_remote_error(err: ChannelRemoteError) -> Exception:
    """Map a sandbox-side exception class name to a sensible main-side one.

    Service-handler errors come back from the sandbox as whatever
    ``services.async_call`` raised — most often :class:`vol.Invalid`. When
    the error frame carries structured ``error_data`` (set for voluptuous
    errors), the original :class:`vol.Invalid` / :class:`vol.MultipleInvalid`
    is rebuilt with its ``path`` intact — callers on main (service/flow
    framework) handle real voluptuous errors correctly. Older/edge frames
    without ``error_data`` fall back to the class-name mapping. Anything we
    don't have a mapping for surfaces as a plain :class:`HomeAssistantError`
    with the remote message preserved.
    """
    if (error_data := err.error_data) is not None:
        kind = error_data.get("kind")
        if kind == "invalid":
            return _rebuild_invalid(error_data)
        if kind == "multiple":
            return vol.MultipleInvalid(
                [_rebuild_invalid(child) for child in error_data.get("errors", [])]
            )
    name = err.error_type or ""
    msg = err.error
    if name in {"Invalid", "MultipleInvalid"}:
        return TypeError(msg)
    if name in {"ServiceNotFound", "ServiceValidationError", "HomeAssistantError"}:
        return HomeAssistantError(msg)
    return HomeAssistantError(f"sandbox error ({name or 'unknown'}): {msg}")


__all__ = [
    "build_service_forwarder",
    "parse_supports_response",
    "translate_remote_error",
]
