"""Network client device class."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.util import dt as dt_util, slugify

from .const import ATTR_DEVICE_TRACKER


class Device:
    """Represents a network device."""

    def __init__(self, mac: str, params: dict[str, Any]) -> None:
        """Initialize the network device."""
        self._mac = mac
        self._params = params
        self._last_seen: datetime | None = None
        self._attrs: dict[str, Any] = {}
        self._wireless_params: dict[str, Any] = {}

    @property
    def name(self) -> str:
        """Return device name."""
        return str(self._params.get("host-name", self.mac))

    @property
    def ip_address(self) -> str | None:
        """Return device primary ip address."""
        return self._params.get("address")

    @property
    def mac(self) -> str:
        """Return device mac."""
        return self._mac

    @property
    def last_seen(self) -> datetime | None:
        """Return device last seen."""
        return self._last_seen

    @property
    def attrs(self) -> dict[str, Any]:
        """Return device attributes."""
        attr_data = self._wireless_params | self._params
        for attr in ATTR_DEVICE_TRACKER:
            if attr in attr_data:
                self._attrs[slugify(attr)] = attr_data[attr]
        return self._attrs

    def update(
        self,
        wireless_params: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        active: bool = False,
    ) -> None:
        """Update Device params."""
        if wireless_params:
            self._wireless_params = wireless_params
        if params:
            self._params = params
        if active:
            self._last_seen = dt_util.utcnow()
