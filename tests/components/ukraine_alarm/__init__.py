"""Tests for the Ukraine Alarm integration."""


def _region(rid, recurse=0, depth=0):
    """Create a test region with optional nested structure."""
    if depth == 0:
        name_prefix = "State"
    elif depth == 1:
        name_prefix = "District"
    else:
        name_prefix = "Community"

    name = f"{name_prefix} {rid}"
    region = {"regionId": rid, "regionName": name, "regionChildIds": []}

    if not recurse:
        return region

    for i in range(1, 4):
        region["regionChildIds"].append(_region(f"{rid}.{i}", recurse - 1, depth + 1))

    return region


REGIONS = {
    "states": [_region(f"{i}", i - 1) for i in range(1, 4)],
}
