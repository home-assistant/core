"""ESPHome discovery data."""

from dataclasses import dataclass

from yarl import URL

from homeassistant.data_entry_flow import BaseServiceInfo


@dataclass(slots=True)
class ESPHomeServiceInfo(BaseServiceInfo):
    """Prepared info from ESPHome entries."""

    name: str
    zwave_home_id: int | None
    ip_address: str
    port: int
    noise_psk: str | None = None
    zigbee_extended_pan_id: int | None = None
    serial_port_name: str | None = None

    @property
    def socket_path(self) -> str:
        """Return the socket path to connect to the ESPHome device."""
        url = URL.build(scheme="esphome", host=self.ip_address, port=self.port)
        if self.noise_psk:
            url = url.with_query({"key": self.noise_psk})
        return str(url)

    def serial_port_path(self, mode: str | None = None) -> str:
        """Return the path of the proxied serial port, framed in the given mode."""
        assert self.serial_port_name is not None

        query = {"port_name": self.serial_port_name}
        if mode is not None:
            query["mode"] = mode
        if self.noise_psk:
            query["key"] = self.noise_psk

        return str(
            URL.build(
                scheme="esphome", host=self.ip_address, port=self.port, path="/"
            ).with_query(query)
        )
