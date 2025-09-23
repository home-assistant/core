"""ESPHome discovery data."""

from dataclasses import dataclass

from yarl import URL

from homeassistant.data_entry_flow import BaseServiceInfo


@dataclass(slots=True)
class ESPHomeServiceInfo(BaseServiceInfo):
    """Prepared info from ESPHome entries."""

    name: str
    zwave_home_id: int
    ip_address: str
    port: int
    noise_psk: str | None = None

    @property
    def socket_path(self) -> str:
        """Return the socket path to connect to the ESPHome device."""
        url = URL.build(scheme="esphome", host=self.ip_address, port=self.port)
        if self.noise_psk:
            url = url.with_user(self.noise_psk)
        return str(url)
