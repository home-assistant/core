"""Shared schema code."""
import voluptuous as vol

CONF_SCHEMA = "schema"
LEGACY = "legacy"
STATE = "state"

MQTT_VACUUM_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_SCHEMA, default=LEGACY): vol.All(
            vol.Lower, vol.Any(LEGACY, STATE)
        )
    }
)


def services_to_strings(services, service_to_string):
    """Convert SUPPORT_* service bitmask to list of service strings."""
    strings = []
    for service in service_to_string:
        if service & services:
            strings.append(service_to_string[service])
    return strings


def strings_to_services(strings, string_to_service):
    """Convert service strings to SUPPORT_* service bitmask."""
    services = 0
    for string in strings:
        services |= string_to_service[string]
    return services
