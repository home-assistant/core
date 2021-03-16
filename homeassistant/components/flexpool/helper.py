"""Helper function for the Flexpool integration."""

units = ["H/s", "KH/s", "MH/s", "GH/s", "TH/s"]


def get_hashrate(hashrate):
    """Convert hashrate to kilohash, megahash etc."""
    unit = 0
    while hashrate > 1000:
        unit += 1
        hashrate = round(hashrate / 1000, 4)

    return round(hashrate, 1), units[unit]
