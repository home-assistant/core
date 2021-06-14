"""The Mikrotik client class."""
from __future__ import annotations

from datetime import datetime

from homeassistant.util import slugify
import homeassistant.util.dt as dt_util

from .const import CLIENT_ATTRIBUTES


class MikrotikClient:
    """Represents a network client."""

    def __init__(self, mac: str, dhcp_params: dict | None = None) -> None:
        """Initialize the client."""
        self._mac = mac
        self.host: str | None = None
        self.dhcp_params: dict = dhcp_params or {}
        self.wireless_params: dict = {}
        self._last_seen: datetime | None = None

    @property
    def name(self):
        """Return client name."""
        return self.dhcp_params.get("host-name", self.mac)

    @property
    def ip_address(self):
        """Return device primary ip address."""
        return self.dhcp_params.get("address")

    @property
    def mac(self):
        """Return client mac."""
        return self._mac

    @property
    def last_seen(self) -> datetime | None:
        """Return client last seen."""
        return self._last_seen

    @property
    def attrs(self) -> dict[str, str]:
        """Return client attributes."""
        attrs = {}
        if self.wireless_params:
            for attr in CLIENT_ATTRIBUTES:
                if attr in self.wireless_params:
                    attrs[slugify(attr)] = self.wireless_params[attr]
        return attrs

    def update(
        self,
        wireless_params: dict | None = None,
        dhcp_params: dict | None = None,
        active: bool = False,
        host: str | None = None,
    ) -> None:
        """Update client params."""
        if host:
            self.host = host
        if wireless_params:
            self.wireless_params = wireless_params
        if dhcp_params:
            self.dhcp_params = dhcp_params
        if active:
            self._last_seen = dt_util.utcnow()
