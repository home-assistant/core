"""Constants for the UniFi Discovery integration."""

from unifi_discovery import UnifiService

DOMAIN = "unifi_discovery"

# Static mapping of UniFi service types to their Home Assistant integration domains.
# This must be static (not a runtime registry) because consumers may not be loaded
# when initial discovery runs — the same pattern DHCP/SSDP use with manifest matchers.
CONSUMER_MAPPING: dict[UnifiService, str] = {
    UnifiService.Access: "unifi_access",
    UnifiService.Network: "unifi",
    UnifiService.Protect: "unifiprotect",
}
