"""Represent Daikin Onecta gateway devices."""

from daikin_onecta.models import GatewayDevice, ManagementPoint


class DaikinOnectaDevice:
    """Class to represent and control one Daikin Onecta Device."""

    def __init__(self, device: GatewayDevice) -> None:
        """Initialize a new Daikin Onecta Device."""
        self.device = device
        self._is_present_in_cloud = True
        self.id: str = device.id
        self.name: str = device.display_name
        self.ha_device_id: str | None = None

    @property
    def present_in_cloud(self) -> bool:
        """Return whether the latest successful response included this gateway."""
        return self._is_present_in_cloud

    @property
    def available(self) -> bool:
        """Return whether the device is connected to the Daikin cloud."""
        return self._is_present_in_cloud and self.device.available

    @property
    def gateway_online(self) -> bool:
        """Return whether the gateway reports an active cloud connection."""
        return self.device.available

    def management_point(self, embedded_id: str) -> ManagementPoint | None:
        """Return a management point by embedded id."""
        return self.device.management_point(embedded_id)

    def set_device_data(self, device: GatewayDevice) -> bool:
        """Overwrite cloud data and return whether device metadata changed."""
        previous_metadata = self._metadata()
        self.device = device
        self.name = device.display_name
        self._is_present_in_cloud = True
        return previous_metadata != self._metadata()

    def mark_unavailable(self) -> None:
        """Mark the device unavailable after it is absent from a cloud response."""
        self._is_present_in_cloud = False

    def _metadata(self) -> tuple[object, ...]:
        """Return the cloud identity and descriptive metadata."""
        model, serial_number, sw_version = self.gateway_metadata
        return (
            self.name,
            self.device.device_model,
            model,
            serial_number,
            sw_version,
            self.device.mac_address,
        )

    @property
    def gateway_metadata(self) -> tuple[str | None, str | None, str | None]:
        """Return model, serial number, and firmware from the gateway point."""
        if (gateway_point := self.device.gateway_management_point) is None:
            return None, None, None
        return gateway_point.model, gateway_point.serial, gateway_point.version
