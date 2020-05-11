"""Mikrotik Client class."""
from homeassistant.const import CONF_IP_ADDRESS, CONF_MAC
from homeassistant.util import slugify
import homeassistant.util.dt as dt_util

from .const import CLIENT_ATTRIBUTES


class MikrotikClient:
    """Represents a network client."""

    def __init__(self, mac, host=None):
        """Initialize the client."""
        self._mac = mac
        self.host = host
        self.dhcp_params = {}
        self.wireless_params = {}
        self._last_seen = None
        self._attrs = {}

    @property
    def name(self):
        """Return client name."""
        return self.dhcp_params.get("host-name", self.mac)

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
        attrs = {}
        attrs[CONF_MAC] = self.mac
        if self.wireless_params:
            for attr in CLIENT_ATTRIBUTES:
                if attr in self.wireless_params:
                    attrs[slugify(attr)] = self.wireless_params[attr]

        ip_address = self.dhcp_params.get("active-address") or self.wireless_params.get(
            "last-ip"
        )
        if ip_address:
            attrs[CONF_IP_ADDRESS] = ip_address
        return attrs

    def update(self, wireless_params=None, dhcp_params=None, active=False, host=None):
        """Update client params."""
        if host:
            self.host = host
        if wireless_params:
            self.wireless_params = wireless_params
        if dhcp_params:
            self.dhcp_params = dhcp_params
        if active:
            self._last_seen = dt_util.utcnow()
