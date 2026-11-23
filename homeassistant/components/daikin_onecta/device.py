"""Represent Daikin Onecta gateway devices."""

from daikin_onecta.models import GatewayDevice, ManagementPoint

from homeassistant.helpers.device_registry import ChildDeviceInfo, DeviceInfo

from .const import DOMAIN

MANAGEMENT_POINT_DEVICE_TRANSLATION_KEYS = {
    "climateControl": "climate_zone",
    "domesticHotWaterFlowThrough": "domestic_hot_water_flow_through",
    "domesticHotWaterTank": "domestic_hot_water_tank",
    "indoorUnit": "indoor_unit",
    "indoorUnitHydro": "indoor_hydro_unit",
    "outdoorUnit": "outdoor_unit",
    "userInterface": "user_interface",
}


def management_point_device_info(
    device: DaikinOnectaDevice, embedded_id: str
) -> DeviceInfo | ChildDeviceInfo:
    """Return consistent device info for a Daikin management point."""
    gateway = device.device
    management_point = device.management_point(embedded_id)
    if management_point is None:
        return _gateway_device_info(device)

    management_point_type = management_point.management_point_type
    if management_point_type == "gateway":
        return _gateway_device_info(device)

    identifier = f"{device.id}_{embedded_id}"
    if management_point_type == "climateControl":
        if len(gateway.management_points_by_type("climateControl")) <= 1:
            return _gateway_device_info(device)
        name = (
            management_point.name.value if management_point.name is not None else None
        )
        return ChildDeviceInfo(
            identifiers={(DOMAIN, identifier)},
            parent_device_id=_gateway_device_id(device, embedded_id),
            translation_key=None if name else "climate_zone",
            name=name,
        )

    return DeviceInfo(
        identifiers={(DOMAIN, identifier)},
        via_device_id=_gateway_device_id(device, embedded_id),
        translation_key=MANAGEMENT_POINT_DEVICE_TRANSLATION_KEYS.get(
            management_point_type, "management_point"
        ),
        sw_version=management_point.version,
    )


def _gateway_device_info(device: DaikinOnectaDevice) -> DeviceInfo:
    """Return Home Assistant device info for a gateway."""
    return DeviceInfo(identifiers={(DOMAIN, device.id)})


def _gateway_device_id(device: DaikinOnectaDevice, embedded_id: str) -> str:
    """Return the registered gateway ID for a management point."""
    if device.ha_device_id is None:
        raise RuntimeError(
            f"Gateway {device.id} is not registered before creating management "
            f"point {embedded_id}"
        )
    return device.ha_device_id


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
            tuple(
                sorted(
                    (point.embedded_id, point.version)
                    for point in self.device.management_points
                    if point.management_point_type not in {"gateway", "climateControl"}
                )
            ),
            tuple(
                sorted(
                    (
                        point.embedded_id,
                        point.name.value if point.name is not None else None,
                    )
                    for point in self.device.management_points
                    if point.management_point_type == "climateControl"
                )
            ),
        )

    @property
    def gateway_metadata(self) -> tuple[str | None, str | None, str | None]:
        """Return model, serial number, and firmware from the gateway point."""
        if (gateway_point := self.device.gateway_management_point) is None:
            return None, None, None
        return gateway_point.model, gateway_point.serial, gateway_point.version
