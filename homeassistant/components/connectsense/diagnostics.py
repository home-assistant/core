from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.const import CONF_HOST

from .const import DOMAIN
from .models import ConnectSenseConfigEntry, ConnectSenseRuntimeData

# Anything in this set will be removed or replaced with REDACTED
TO_REDACT: set[str] = {
    CONF_HOST,                       # hostnames / IPs
    "webhook_id",                    # internal webhook id
    "webhook_url",                   # if you cache it
    "webhook_token_current",         # tokens (current)
    "webhook_token_prev",            # tokens (previous)
    "webhook_token_prev_valid_until",
    "last_actor",                    # HA username cached for notifications
    "certificate",                   # just in case you cache any cert material
    "private_key",
    "mac", "mac_address", "MAC",     # defensive: different casings
}

def _safe_copy(obj: Any) -> Any:
    """Return a JSON-serializable shallow copy with basic normalization."""
    if isinstance(obj, dict):
        return {k: _safe_copy(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_safe_copy(v) for v in obj]
    # Leave primitives as-is
    return obj

async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConnectSenseConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    # Pull per-entry runtime store
    runtime: ConnectSenseRuntimeData | None = getattr(entry, "runtime_data", None)
    store = runtime.store if runtime else hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    state = store.get("state", {})

    # Device & entity registry context
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)

    # Resolve the device created for this entry
    # Entities use identifiers={(DOMAIN, entry.unique_id or host)}
    # Work out the identifier key used in device_info
    ident_key = (DOMAIN, (entry.unique_id or entry.data.get(CONF_HOST)))
    device = dev_reg.async_get_device(identifiers={ident_key})

    # Collect entities attached to that device (if any)
    entity_summaries: list[dict[str, Any]] = []
    if device:
        for entity_id in ent_reg.entities:
            ent = ent_reg.entities.get(entity_id)
            if ent and ent.device_id == device.id and ent.platform == DOMAIN:
                entity_summaries.append(
                    {
                        "entity_id": ent.entity_id,
                        "domain": ent.domain,
                        "unique_id": ent.unique_id,
                        "original_name": ent.original_name,
                        "disabled_by": str(ent.disabled_by) if ent.disabled_by else None,
                    }
                )

    # Build the payload (use shallow copies so we don’t mutate live objects)
    payload: dict[str, Any] = {
        "config_entry": {
            "entry_id": entry.entry_id,
            "title": entry.title,
            "unique_id": entry.unique_id,
            "data": _safe_copy(dict(entry.data)),
            "options": _safe_copy(dict(entry.options)),
            "version": entry.version,
            "domain": entry.domain,
            "source": entry.source,
        },
        "integration_runtime": {
            "store": _safe_copy({k: v for k, v in store.items() if k != "state"}),
            "state": _safe_copy(state),
        },
        "device_registry": {
            "device": {
                "id": getattr(device, "id", None),
                "name": getattr(device, "name", None),
                "identifiers": list(getattr(device, "identifiers", [])) if device else None,
                "manufacturer": getattr(device, "manufacturer", None) if device else None,
                "model": getattr(device, "model", None) if device else None,
                "sw_version": getattr(device, "sw_version", None) if device else None,
                "hw_version": getattr(device, "hw_version", None) if device else None,
                "configuration_url": getattr(device, "configuration_url", None) if device else None,
            },
            "entities": entity_summaries,
        },
    }

    # Redact sensitive bits everywhere in the payload
    return async_redact_data(payload, TO_REDACT)
