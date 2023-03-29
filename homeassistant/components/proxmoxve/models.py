"""Models for Proxmox VE integration."""

import dataclasses


@dataclasses.dataclass
class ProxmoxVMData:
    """All data parsed from the Proxmox API."""

    name: str
    status: str
