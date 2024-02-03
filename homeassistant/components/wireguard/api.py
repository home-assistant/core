"""API for the WIreGuard integration."""
from dataclasses import dataclass
from datetime import UTC, datetime as dt

import requests

from .const import ATTR_LATEST_HANDSHAKE, ATTR_TRANSFER_RX, ATTR_TRANSFER_TX


@dataclass(frozen=True)
class WireGuardPeer:
    """Device for the WireGuard API."""

    name: str
    latest_handshake: dt | None
    transfer_rx: int
    transfer_tx: int


class WireGuardAPI:
    """WireGuard status API."""

    def __init__(self, host: str) -> None:
        """Initialize."""
        self.host: str = host

    def get_status(self) -> dict[str, dict[str, str | int]]:
        """Get the WireGuard status info."""
        try:
            with requests.get(self.host, timeout=5) as response:
                return response.json()
        except requests.RequestException as err:
            raise WireGuardError from err

    @property
    def peers(self) -> list[WireGuardPeer]:
        """List of WireGuard peers."""
        status_data = self.get_status()
        return [peer_from_data(name, data) for name, data in status_data.items()]


class WireGuardError(requests.RequestException):
    """WireGuard request error."""


def peer_from_data(name: str, data: dict[str, str | int]) -> WireGuardPeer:
    """Parse the entry data into a WireGuardPeer."""
    return WireGuardPeer(
        name=name,
        latest_handshake=(
            dt.fromtimestamp(float(data[ATTR_LATEST_HANDSHAKE]), UTC)
            if int(data[ATTR_LATEST_HANDSHAKE]) > 0
            else None
        ),
        transfer_rx=int(data[ATTR_TRANSFER_RX]),
        transfer_tx=int(data[ATTR_TRANSFER_TX]),
    )
