"""Model definitions for Actiontec MI424WR (Verizon FIOS) routers."""

from dataclasses import dataclass


@dataclass
class Device:
    """Actiontec device class."""

    ip_address: str
    mac_address: str
    timevalid: int
