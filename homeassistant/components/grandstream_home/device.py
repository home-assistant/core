"""Device definitions for Grandstream Home."""

import contextlib

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo, format_mac

from .const import DEVICE_TYPE_GDS, DEVICE_TYPE_GNS_NAS, DOMAIN


class GrandstreamDevice:
    """Grandstream device base class."""

    device_type: str | None = None  # will be set in subclasses
    device_model: str | None = None  # Original device model (GDS/GSC/GNS)
    product_model: str | None = (
        None  # Specific product model (e.g., GDS3725, GDS3727, GSC3560)
    )
    ip_address: str | None = None  # Device IP address
    mac_address: str | None = None  # Device MAC address
    firmware_version: str | None = None  # Device firmware version

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
        self._register_device()

    def set_ip_address(self, ip_address: str) -> None:
        """Set device IP address."""
        self.ip_address = ip_address
        # Update device registry information
        if self.ip_address:
            self._register_device()

    def set_mac_address(self, mac_address: str) -> None:
        """Set device MAC address."""
        self.mac_address = mac_address
        # Update device registry information
        if self.mac_address:
            self._register_device()

    def set_firmware_version(self, firmware_version: str) -> None:
        """Set device firmware version."""
        self.firmware_version = firmware_version
        # Update device registry information
        # Only register if config entry still exists
        if self.firmware_version:
            with contextlib.suppress(HomeAssistantError):
                self._register_device()

    def _get_display_model(self) -> str:
        """Get the model string to display in device info.

        Priority: product_model > device_model > device_type
        """
        if self.product_model:
            return self.product_model
        if self.device_model:
            return self.device_model
        return self.device_type or "Unknown"

    def _register_device(self) -> None:
        """Register device in Home Assistant."""
        device_registry = dr.async_get(self.hass)

        # Prepare model info (including IP address)
        display_model = self._get_display_model()
        model_info = display_model
        if self.ip_address:
            model_info = f"{display_model} (IP: {self.ip_address})"

        # Determine sw_version: prefer firmware version, fallback to integration version
        sw_version = self.firmware_version or "unknown"

        # Prepare connections (MAC address) using HA standard format
        connections: set[tuple[str, str]] = set()
        if self.mac_address:
            # Use HA's format_mac for standard format: "aa:bb:cc:dd:ee:ff"
            connections.add(("mac", format_mac(self.mac_address)))

        # Use async_get_or_create which automatically handles:
        # 1. Matching by identifiers -> update existing device
        # 2. Matching by connections (MAC) -> update existing device
        # 3. No match -> create new device
        device_registry.async_get_or_create(
            config_entry_id=self.config_entry_id,
            identifiers={(DOMAIN, self.unique_id)},
            name=self.name,
            manufacturer="Grandstream",
            model=model_info,
            suggested_area="Entry",
            sw_version=sw_version,
            connections=connections,
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        # Prepare model info (including IP address)
        display_model = self._get_display_model()
        model_info = display_model
        if self.ip_address:
            model_info = f"{display_model} (IP: {self.ip_address})"

        # Determine sw_version: prefer firmware version, fallback to integration version
        sw_version = self.firmware_version or "unknown"

        # Prepare connections (MAC address) using HA standard format
        connections: set[tuple[str, str]] = set()
        if self.mac_address:
            # Use HA's format_mac for standard format: "aa:bb:cc:dd:ee:ff"
            connections.add(("mac", format_mac(self.mac_address)))

        return DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            name=self.name,
            manufacturer="Grandstream",
            model=model_info,
            suggested_area="Entry",
            sw_version=sw_version,
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
