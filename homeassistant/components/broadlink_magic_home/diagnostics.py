"""Diagnostics support for Broadlink Magic Home."""

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import BroadLinkMagicConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BroadLinkMagicConfigEntry
) -> dict[str, Any]:
    """Return an allowlist of family fields without identifiers.

    Tokens, MACs, DIDs, family and device names and peer addresses are left
    out entirely instead of being redacted.
    """
    coordinator = entry.runtime_data
    family = coordinator.family
    gateway_set = coordinator.gateway_set
    online = {gateway.mac for gateway in gateway_set.online_gateways}
    return {
        "family": {
            "rooms": len(family.rooms),
            "devices": len(family.devices),
            "groups": len(family.groups),
            "scenes": len(family.scenes),
        },
        "gateways": [
            {"online": gateway.mac in online, "has_peer": gateway.peer is not None}
            for gateway in gateway_set.gateways
        ],
        "devices": [
            {
                "kind": device.kind.value,
                "ble_category": device.ble_category,
                "ble_device_type": device.ble_device_type,
                "pid": device.effective_pid,
                "version": device.version,
                "short_addr": device.short_addr,
                "is_rm_child": device.is_rm_child,
                "rm_profile": device.rm_profile.value if device.rm_profile else None,
                "channel_count": device.channel_count,
                "state": coordinator.device_states.get(device.stable_id, {}),
                "reports": coordinator.report_serials.get(device.stable_id, 0),
            }
            for device in family.devices
        ],
    }
