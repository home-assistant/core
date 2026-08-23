"""Diagnostics support for Hot Spring."""

from dataclasses import asdict
import re
from typing import Any

from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .coordinator import HotSpringConfigEntry

TO_REDACT = {
    CONF_HOST,
}


def _redact_mac(value: str, patterns: list[str]) -> str:
    """Redact MAC address patterns from a string."""
    for pattern in patterns:
        value = re.sub(re.escape(pattern), REDACTED, value, flags=re.IGNORECASE)
    return value


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HotSpringConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    spa = coordinator.data

    info = asdict(spa.info)
    if mac_address := spa.info.mac_address:
        clean_mac = mac_address.replace(":", "")
        patterns = [mac_address, clean_mac, clean_mac[-6:]]
        info["root_topic"] = _redact_mac(info["root_topic"], patterns)
        info["hostname"] = _redact_mac(info["hostname"], patterns)

    return {
        "entry": async_redact_data(entry.data, TO_REDACT),
        "data": {
            "info": info,
            "heater": asdict(spa.heater),
            "jets": [asdict(jet) for jet in spa.jets],
            "blower": asdict(spa.blower),
            "light_zones": [asdict(zone) for zone in spa.light_zones],
            "logo_light": asdict(spa.logo_light),
            "clean_cycle": asdict(spa.clean_cycle),
            "spa_lock": asdict(spa.spa_lock),
            "water_care": asdict(spa.water_care),
            "freshwater_iq": asdict(spa.freshwater_iq),
            "energy_savings": [asdict(schedule) for schedule in spa.energy_savings],
            "versions": asdict(spa.versions),
            "connection_status": asdict(spa.connection_status),
            "diagnostics": asdict(spa.diagnostics),
            "test_metrics": asdict(spa.test_metrics),
        },
    }
