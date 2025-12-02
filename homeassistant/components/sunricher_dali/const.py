"""Constants for the Sunricher DALI integration."""

DOMAIN = "sunricher_dali"
MANUFACTURER = "Sunricher"
CONF_SERIAL_NUMBER = "serial_number"


def sn_to_mac(serial_number: str) -> str:
    """Convert serial number to MAC address format (6A242121110E -> 6a:24:21:21:11:0e)."""
    sn = serial_number.lower().strip()
    if len(sn) != 12:
        raise ValueError(f"Invalid serial number length: {len(sn)}, expected 12")
    return ":".join(sn[i : i + 2] for i in range(0, 12, 2))
