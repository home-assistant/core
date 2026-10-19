"""Diagnostics support for UniFi Network."""

from typing import Any, cast

from uiprotect.anonymize import anonymize_data
from uiprotect.data.public_bootstrap import PublicBootstrap

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .data import UFPConfigEntry

# anonymize_data covers the private-tree keys; the public camera payload
# carries the stream URLs (host + secret alias) under its own key.
TO_REDACT = {"rtspsStreams"}


# Device stores of the public cache; liveviews, users and arm profiles are
# configuration, not devices.
_PUBLIC_DEVICE_STORES = (
    "cameras",
    "lights",
    "sensors",
    "chimes",
    "viewers",
    "sirens",
    "relays",
    "fobs",
    "speakers",
    "link_stations",
    "bridges",
)


def _public_cache(pb: PublicBootstrap) -> dict[str, Any]:
    """Return the anonymized public cache."""
    public: dict[str, Any] = {
        "nvr": anonymize_data(pb.nvr.unifi_dict()) if pb.nvr is not None else None,
        "arm_mode": pb.arm_mode is not None,
    }
    for store in _PUBLIC_DEVICE_STORES:
        public[store] = [
            async_redact_data(
                cast(dict[str, Any], anonymize_data(device.unifi_dict())), TO_REDACT
            )
            for device in getattr(pb, store).values()
        ]
    return public


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: UFPConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    api = config_entry.runtime_data.api
    diagnostics: dict[str, Any] = {"options": dict(config_entry.options)}
    if not api.is_public_only:
        diagnostics["bootstrap"] = anonymize_data(api.bootstrap.unifi_dict())
    if api.has_public_bootstrap:
        diagnostics["public_bootstrap"] = _public_cache(api.public_bootstrap)
    return diagnostics
