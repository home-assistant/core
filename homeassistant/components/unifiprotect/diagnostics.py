"""Diagnostics support for UniFi Network."""

from typing import Any, cast

from uiprotect.test_util.anonymize import anonymize_data

from homeassistant.core import HomeAssistant

from .data import UFPConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: UFPConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    data = config_entry.runtime_data
    api = data.api
    if api.is_public_only:
        # No private bootstrap in API-key-only mode; dump the public cache.
        pb = api.public_bootstrap
        public = {
            "nvr": anonymize_data(pb.nvr.unifi_dict()) if pb.nvr is not None else None,
            "cameras": [
                anonymize_data(camera.unifi_dict()) for camera in pb.cameras.values()
            ],
            "arm_mode": pb.arm_mode is not None,
        }
        return {"public_bootstrap": public, "options": dict(config_entry.options)}
    bootstrap = cast(dict[str, Any], anonymize_data(api.bootstrap.unifi_dict()))
    return {"bootstrap": bootstrap, "options": dict(config_entry.options)}
