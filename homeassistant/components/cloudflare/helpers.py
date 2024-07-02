"""Helpers for the CloudFlare integration."""

import pycfdns


def get_zone_id(target_zone_name: str, zones: list[pycfdns.ZoneModel]) -> str | None:
    """Get the zone ID for the target zone name."""
    for zone in zones:
        if zone["name"] == target_zone_name:
            return zone["id"]
    return None
