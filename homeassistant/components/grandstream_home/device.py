"""Device definitions for Grandstream Home."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo, format_mac

from .const import DEVICE_TYPE_GDS, DEVICE_TYPE_GNS_NAS, DOMAIN


class GrandstreamDevice:
    """Grandstream device base class."""

    device_type: str | None = None
    device_model: str | None = None
    product_model: str | None = None
    ip_address: str | None = None
    mac_address: str | None = None
    firmware_version: str | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        unique_id: str,
        config_entry_id: str,
        device_model: str | None = None,
        product_model: str | None = None,
    ) -> None:
        """Initialize the device."""
        self.hass = hass
        self.name = name
        self.unique_id = unique_id
        self.config_entry_id = config_entry_id
        self.device_model = device_model
        self.product_model = product_model

    def set_ip_address(self, ip_address: str) -> None:
        """Set device IP address."""
        self.ip_address = ip_address

    def set_mac_address(self, mac_address: str) -> None:
        """Set device MAC address."""
        self.mac_address = mac_address

    def set_firmware_version(self, firmware_version: str) -> None:
        """Set device firmware version."""
        self.firmware_version = firmware_version

    def _get_display_model(self) -> str:
        """Get the model string to display in device info."""
        if self.product_model:
            return self.product_model
        if self.device_model:
            return self.device_model
        return self.device_type or "Unknown"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        display_model = self._get_display_model()
        model_info = display_model
        if self.ip_address:
            model_info = f"{display_model} (IP: {self.ip_address})"

        connections: set[tuple[str, str]] = set()
        if self.mac_address:
            connections.add(("mac", format_mac(self.mac_address)))

        return DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            name=self.name,
            manufacturer="Grandstream",
            model=model_info,
            suggested_area="Entry",
            sw_version=self.firmware_version or "unknown",
            connections=connections or set(),
        )


class GDSDevice(GrandstreamDevice):
    """GDS device."""

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        unique_id: str,
        config_entry_id: str,
        device_model: str | None = None,
        product_model: str | None = None,
    ) -> None:
        """Initialize the device."""
        super().__init__(
            hass, name, unique_id, config_entry_id, device_model, product_model
        )
        self.device_type = DEVICE_TYPE_GDS


class GNSNASDevice(GrandstreamDevice):
    """GNS NAS device."""

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        unique_id: str,
        config_entry_id: str,
        device_model: str | None = None,
        product_model: str | None = None,
    ) -> None:
        """Initialize the device."""
        super().__init__(
            hass, name, unique_id, config_entry_id, device_model, product_model
        )
        self.device_type = DEVICE_TYPE_GNS_NAS
