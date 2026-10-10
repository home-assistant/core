"""Represent Daikin Onecta gateway devices."""

from daikin_onecta.models import GatewayDevice, ManagementPoint

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

from .const import DOMAIN


class DaikinOnectaDevice:
    """Class to represent and control one Daikin Onecta Device."""

    def __init__(self, device: GatewayDevice) -> None:
        """Initialize a new Daikin Onecta Device."""
        self.device = device
        self._is_present_in_cloud = True
        self.id: str = device.id
        self.name: str = device.display_name

    @property
    def present_in_cloud(self) -> bool:
        """Return whether the latest successful response included this gateway."""
        return self._is_present_in_cloud

    @property
    def available(self) -> bool:
        """Return whether the device is connected to the Daikin cloud."""
        return self._is_present_in_cloud and self.device.available

    def management_point(self, embedded_id: str) -> ManagementPoint | None:
        """Return a management point by embedded id."""
        return self.device.management_point(embedded_id)

    @property
    def gateway_embedded_id(self) -> str | None:
        """Return the embedded ID of the gateway management point."""
        return self.device.gateway_embedded_id

    def set_device_data(self, device: GatewayDevice) -> bool:
        """Overwrite cloud data and return whether registry metadata changed."""
        previous_metadata = self._device_registry_metadata()
        self.device = device
        self.name = device.display_name
        self._is_present_in_cloud = True
        return previous_metadata != self._device_registry_metadata()

    def mark_unavailable(self) -> None:
        """Mark the device unavailable after it is absent from a cloud response."""
        self._is_present_in_cloud = False

    def async_update_device_registry(
        self, hass: HomeAssistant, config_entry: ConfigEntry
    ) -> None:
        """Refresh gateway metadata in the Home Assistant device registry."""
        gateway = self.device
        connections = (
            {(CONNECTION_NETWORK_MAC, gateway.mac_address)}
            if gateway.mac_address
            else set()
        )
        model, serial_number, sw_version = self._gateway_metadata()
        dr.async_get(hass).async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={(DOMAIN, self.id)},
            connections=connections,
            manufacturer="Daikin",
            model=model,
            model_id=gateway.device_model,
            name=self.name,
            serial_number=serial_number,
            sw_version=sw_version,
        )

    def _device_registry_metadata(
        self,
    ) -> tuple[str, str | None, str | None, str | None, str | None]:
        """Return the cloud fields mirrored in the device registry."""
        model, serial_number, sw_version = self._gateway_metadata()
        return self.name, self.device.device_model, model, serial_number, sw_version

    def _gateway_metadata(self) -> tuple[str | None, str | None, str | None]:
        """Return model, serial number, and firmware from the gateway point."""
        gateway = self.device
        if (embedded_id := gateway.gateway_embedded_id) is not None and (
            management_point := gateway.management_point(embedded_id)
        ) is not None:
            return (
                management_point.model,
                management_point.serial,
                management_point.version,
            )
        return None, None, None
