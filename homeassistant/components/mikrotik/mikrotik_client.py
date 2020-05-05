"""Mikrotik Client class."""
from homeassistant.util import slugify
import homeassistant.util.dt as dt_util

from .const import ATTR_DEVICE_TRACKER


class MikrotikClient:
    """Represents a network client."""

    def __init__(self, mac, params, hub_id):
        """Initialize the client."""
        self._mac = mac
        self._params = params
        self._last_seen = None
        self._attrs = {}
        self._wireless_params = {}
        self.hub_id = hub_id

    @property
    def name(self):
        """Return client name."""
        return self._params.get("host-name", self.mac)

    @property
    def mac(self):
        """Return client mac."""
        return self._mac

    @property
    def last_seen(self):
        """Return client last seen."""
        return self._last_seen

    @property
    def attrs(self):
        """Return client attributes."""
        attr_data = self._wireless_params or self._params
        for attr in ATTR_DEVICE_TRACKER:
            if attr in attr_data:
                self._attrs[slugify(attr)] = attr_data[attr]
        self._attrs["ip_address"] = self._params.get(
            "active-address", self._wireless_params.get("last-ip")
        )
        return self._attrs

    def update(self, wireless_params=None, params=None, active=False, hub_id=None):
        """Update client params."""
        if hub_id:
            self.hub_id = hub_id
        if wireless_params:
            self._wireless_params = wireless_params
        if params:
            self._params = params
        if active:
            self._last_seen = dt_util.utcnow()
