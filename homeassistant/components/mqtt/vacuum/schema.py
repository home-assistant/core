"""Shared schema code."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.vacuum import VacuumEntityFeature

from ..const import CONF_SCHEMA

LEGACY = "legacy"
STATE = "state"

MQTT_VACUUM_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_SCHEMA, default=LEGACY): vol.All(
            vol.Lower, vol.Any(LEGACY, STATE)
        )
    }
)


def services_to_strings(
    services: VacuumEntityFeature,
    service_to_string: dict[VacuumEntityFeature, str],
) -> list[str]:
    """Convert SUPPORT_* service bitmask to list of service strings."""
    return [
        service_to_string[service]
        for service in service_to_string
        if service & services
    ]


def strings_to_services(
    strings: list[str], string_to_service: dict[str, VacuumEntityFeature]
) -> VacuumEntityFeature:
    """Convert service strings to SUPPORT_* service bitmask."""
    services = VacuumEntityFeature(0)
    for string in strings:
        services |= string_to_service[string]
    return services
