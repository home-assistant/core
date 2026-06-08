"""Diagnostics support for A Better Routeplanner."""

import base64
import binascii
from dataclasses import asdict
import json
from typing import Any, cast

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.update_coordinator import TimestampDataUpdateCoordinator

from . import AbetterrouteplannerConfigEntry
from .const import CONF_KNOWN_VEHICLE_IDS, CONF_VEHICLE_IDS

# ``async_redact_data`` recurses into nested dicts and lists; any matching key
# at any depth is redacted. ``token`` blanks the whole OAuth subtree (access /
# refresh / id_token); ``name`` covers ``AbrpVehicle.name`` (an OIDC
# ``name`` claim never reaches a key-match here because the id_token claims
# go through the allowlist filter below instead of ``async_redact_data``).
TO_REDACT = {
    "token",
    "name",
}

# Strict allowlist for OIDC id_token claims surfaced to diagnostics. Standard
# RFC-7519 / OpenID Connect Core metadata claims only — they carry no PII and
# stay stable across IdP key rotations. Any other claim (``name``, ``email``,
# ``sub``, ``preferred_username``, ``picture``, ``address``, future ABRP-
# specific additions, etc.) is replaced with ``**REDACTED**`` so a future
# IdP that ships a new PII-bearing claim cannot silently leak through.
_REDACTED = "**REDACTED**"
_ALLOWED_ID_TOKEN_CLAIMS: frozenset[str] = frozenset(
    {"iss", "aud", "iat", "exp", "nbf", "jti", "azp", "auth_time", "acr", "amr"}
)


def _decode_id_token_claims(id_token: str) -> dict[str, Any] | None:
    """Best-effort decode of the unverified id_token payload for triage display.

    Mirrors :func:`config_flow._decode_jwt_payload`. Returns ``None`` on any
    failure so the diagnostics output stays consistent even when the token
    shape is unexpected (rotated IdP key, truncated grant, sentinel test
    payload, non-string corrupted storage, etc.). The exception band covers
    every realistic failure mode of the standard unverified-JWT decode idiom:
    :class:`ValueError`, :class:`IndexError`, :class:`KeyError`,
    :class:`TypeError`, plus :class:`binascii.Error` for malformed base64 and
    :class:`AttributeError` for non-string inputs (e.g. a corrupted
    ``.storage`` entry whose ``id_token`` is a dict).
    """
    try:
        payload_b64 = id_token.split(".")[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)
        return cast(dict[str, Any], json.loads(base64.urlsafe_b64decode(payload_b64)))
    except ValueError, IndexError, KeyError, TypeError, AttributeError, binascii.Error:
        return None


def _filter_id_token_claims(claims: dict[str, Any]) -> dict[str, Any]:
    """Apply the allowlist filter to id_token claims.

    Allowlisted keys pass their values through verbatim; any other key
    surfaces as ``"**REDACTED**"`` so the diagnostics output still records
    that the claim was present (useful triage when an unexpected claim
    appears) without leaking its value. Allowlist-shape protects against
    future IdP claim additions silently leaking through.
    """
    return {
        key: value if key in _ALLOWED_ID_TOKEN_CLAIMS else _REDACTED
        for key, value in claims.items()
    }


def _summarize_coordinator(
    coord: TimestampDataUpdateCoordinator[Any],
) -> dict[str, Any]:
    """Summarize a coordinator's framework state for diagnostics triage.

    For the polling (garage) coordinator, ``last_update_success_time`` is set
    by the framework's ``_async_refresh_finished`` after each successful
    ``_async_update_data``. For the push (telemetry) coordinator,
    ``async_set_updated_data`` does NOT invoke ``_async_refresh_finished``,
    so :meth:`AbrpTelemetryCoordinator.apply_frame` stamps the field
    explicitly after each merged SSE frame. The diagnostics consumer reads a
    consistent "when did this last work" signal across both coordinators.
    """
    return {
        "last_update_success": coord.last_update_success,
        "last_update_success_time": (
            coord.last_update_success_time.isoformat()
            if coord.last_update_success_time
            else None
        ),
        "last_exception_type": (
            type(coord.last_exception).__name__ if coord.last_exception else None
        ),
        "update_interval_seconds": (
            coord.update_interval.total_seconds() if coord.update_interval else None
        ),
        # Privileged read of the framework's listener registry — diagnostics
        # is the documented consumer of debug-only coordinator attributes.
        "listener_count": len(coord._listeners),  # noqa: SLF001
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: AbetterrouteplannerConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry.

    Token material is wholesale-redacted via :data:`TO_REDACT`; id_token
    claims are decoded fresh at call time because :mod:`config_flow` only
    stores the raw id_token in ``entry.data["token"]["id_token"]`` and not
    the decoded claims. Internal coordinator attributes
    (``_presence_predicates``, ``_presence_seen``, ``_listeners``) are read
    directly — diagnostics is the privileged consumer of those debug-only
    surfaces.
    """
    runtime = entry.runtime_data
    # Direct access: OAuth helper guarantees ``token`` on any LOADED entry,
    # and the diagnostics UI gates the download on LOADED state.
    token = entry.data["token"]
    # ``.get()``: id_token is optional in the OAuth spec and absent during
    # certain reauth corner cases. ``token_type`` / ``expires_at`` are
    # likewise OAuth-spec-optional even though the helper writes them in
    # normal flow.
    id_token = token.get("id_token")
    claims = _decode_id_token_claims(id_token) if id_token else None

    # ``CONF_VEHICLE_IDS`` is set on every entry by the config-flow picker, so
    # direct access is correct. ``CONF_KNOWN_VEHICLE_IDS`` is an additive
    # field; pre-upgrade entries may still lack it until the listener's
    # deferred seed runs, so the diagnostics call site stays defensive.
    selected = set(entry.data[CONF_VEHICLE_IDS])
    known = set(entry.data.get(CONF_KNOWN_VEHICLE_IDS, []))

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    # Group by entity domain (``sensor`` / ``binary_sensor`` / ...), not by
    # the registry's ``.platform`` attribute — the latter stores the
    # integration name, so grouping by it produces a degenerate
    # ``{"abetterrouteplanner": N}`` shape that loses triage value.
    entities_by_domain: dict[str, int] = {}
    for ent in entities:
        entities_by_domain[ent.domain] = entities_by_domain.get(ent.domain, 0) + 1

    telemetry = runtime.telemetry_coordinator

    return {
        "entry": {
            "entry_id": entry.entry_id,
            # ``entry.title`` is auto-generated as
            # ``f"{flow_impl.name} ({display_name})"``; surfacing it verbatim
            # would leak the OIDC display-name PII. Boolean carries the
            # triage signal (does the title follow the auto-generated
            # shape?) without exposing the user-identifying suffix. Title
            # rename in the UI also flips this to False.
            "title_includes_display_name": "(" in (entry.title or ""),
            "version": entry.version,
            "source": entry.source,
            "selected_vehicle_ids": sorted(selected),
            "known_vehicle_ids": sorted(known),
            "declined_vehicle_ids": sorted(known - selected),
            "data": async_redact_data(entry.data, TO_REDACT),
        },
        "token_metadata": {
            "token_type": token.get("token_type"),
            "expires_at": token.get("expires_at"),
            "has_id_token": id_token is not None,
        },
        "id_token_claims": _filter_id_token_claims(claims) if claims else {},
        "garage_coordinator": _summarize_coordinator(runtime.garage_coordinator),
        "telemetry_coordinator": {
            **_summarize_coordinator(telemetry),
            "presence_predicates_registered": sorted(telemetry._presence_predicates),  # noqa: SLF001
            "presence_seen": sorted(
                list(pair)
                for pair in telemetry._presence_seen  # noqa: SLF001
            ),
            # Per-vehicle, per-metric upstream provider stamps surfaced
            # verbatim for triage ("why isn't Tesla telemetry flowing?").
            # Provider strings are a closed public enum (see
            # ``_telemetry_models.Provider``) — no PII, no redaction.
            "providers": {
                str(vid): dict(by_key)
                for vid, by_key in telemetry.last_provider.items()
            },
        },
        "garage": async_redact_data(
            [asdict(v) for v in runtime.garage_coordinator.data],
            TO_REDACT,
        ),
        # Surface FIELD NAMES per vehicle, not raw values: the SSE wire
        # payload can carry GPS coordinates (``location.lat``/``long``),
        # odometer (``odometer.m``), speed (``speed.kph``), heading,
        # elevation, and other future PII-bearing metrics. Diagnostics-
        # in-public-issues must not leak the user's exact vehicle location.
        # Field names alone answer the "is X working for this vehicle?"
        # triage question without spilling values.
        "telemetry_field_names": {
            str(vid): sorted(frame) for vid, frame in telemetry.data.items()
        },
        "sse_state": dict(telemetry.sse_state),
        "registry": {
            "device_count": len(devices),
            "entity_count": len(entities),
            "entities_by_domain": entities_by_domain,
        },
    }
