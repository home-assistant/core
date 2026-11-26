"""Diagnostics support for Google Cast."""

from typing import Any

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.const import CONF_UUID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import CastConfigEntry
from .const import CONF_IGNORE_CEC, CONF_KNOWN_HOSTS, DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: CastConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime_data = entry.runtime_data
    browser = runtime_data.browser
    cast_infos = list(browser.devices.values()) if browser else []
    entity_registry = er.async_get(hass)
    return {
        "config": {
            "known_hosts_count": len(entry.data.get(CONF_KNOWN_HOSTS) or []),
            "uuid_filter_count": len(entry.data.get(CONF_UUID) or []),
            "ignore_cec_count": len(entry.data.get(CONF_IGNORE_CEC) or []),
        },
        "devices": [
            {
                "model_name": cast_info.model_name,
                "manufacturer": cast_info.manufacturer,
                "cast_type": cast_info.cast_type,
                "port": cast_info.port,
                # Dynamic groups are handled but have no entity
                "added": cast_info.uuid in runtime_data.added_cast_devices
                and entity_registry.async_get_entity_id(
                    MEDIA_PLAYER_DOMAIN, DOMAIN, str(cast_info.uuid)
                )
                is not None,
            }
            for cast_info in cast_infos
        ],
        "unknown_models": {
            str(model_name): {"cast_type": cast_type, "manufacturer": manufacturer}
            # Copy since the discovery thread mutates it
            for model_name, (cast_type, manufacturer) in list(
                runtime_data.unknown_models.items()
            )
        },
    }
