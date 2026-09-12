"""Base entity for the SMA Modbus integration."""

from enum import IntEnum

from sma_modbus import SmaComponent
from sma_modbus.home_manager import SunnyHomeManagerModel
from sma_modbus.sunny_boy import SunnyBoyModel
from sma_modbus.sunny_boy_smart_energy import SunnyBoySmartEnergyModel
from sma_modbus.sunny_tripower import SunnyTripowerModel

from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_WEB_PORT, DEVICE_NAMES, DOMAIN
from .coordinator import SmaCoordinator

# Human-readable product names for each device model, sourced from the
# SMA Modbus parameter lists.
_MODEL_NAMES: dict[IntEnum, str] = {
    SunnyHomeManagerModel.SUNNY_HOME_MANAGER: "Sunny Home Manager 2.0",
    SunnyBoyModel.SB_3_0: "Sunny Boy 3.0",
    SunnyBoyModel.SB_3_6: "Sunny Boy 3.6",
    SunnyBoyModel.SB_4_0: "Sunny Boy 4.0",
    SunnyBoyModel.SB_5_0: "Sunny Boy 5.0",
    SunnyBoyModel.SB_6_0: "Sunny Boy 6.0",
    SunnyBoySmartEnergyModel.SBSE_3_6: "Sunny Boy Smart Energy 3.6",
    SunnyBoySmartEnergyModel.SBSE_3_8_US: "Sunny Boy Smart Energy 3.8-US",
    SunnyBoySmartEnergyModel.SBSE_4_0: "Sunny Boy Smart Energy 4.0",
    SunnyBoySmartEnergyModel.SBSE_4_8_US: "Sunny Boy Smart Energy 4.8-US",
    SunnyBoySmartEnergyModel.SBSE_5_0: "Sunny Boy Smart Energy 5.0",
    SunnyBoySmartEnergyModel.SBSE_5_8_US: "Sunny Boy Smart Energy 5.8-US",
    SunnyBoySmartEnergyModel.SBSE_6_0: "Sunny Boy Smart Energy 6.0",
    SunnyBoySmartEnergyModel.SBSE_7_7_US: "Sunny Boy Smart Energy 7.7-US",
    SunnyBoySmartEnergyModel.SBSE_8_0: "Sunny Boy Smart Energy 8.0",
    SunnyBoySmartEnergyModel.SBSE_9_6_US: "Sunny Boy Smart Energy 9.6-US",
    SunnyBoySmartEnergyModel.SBSE_9_9: "Sunny Boy Smart Energy 9.9",
    SunnyBoySmartEnergyModel.SBSE_11_5_US: "Sunny Boy Smart Energy 11.5-US",
    SunnyTripowerModel.STP_3_0: "Sunny Tripower 3.0",
    SunnyTripowerModel.STP_4_0: "Sunny Tripower 4.0",
    SunnyTripowerModel.STP_5_0: "Sunny Tripower 5.0",
    SunnyTripowerModel.STP_6_0: "Sunny Tripower 6.0",
}


class SmaEntity(CoordinatorEntity[SmaCoordinator]):
    """Defines a SMA coordinator entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SmaCoordinator) -> None:
        """Initialize a SMA entity."""
        super().__init__(coordinator)
        device = coordinator.device

        # Type Label fields (vendor, serial, firmware, device_type) are
        # available on all device models; fall back to static defaults when
        # a device does not report them.
        vendor = getattr(device, "vendor", None)
        device_type = getattr(device, "device_type", None)
        serial_number = getattr(device, "serial_number", None)
        firmware_version = getattr(device, "firmware_version", None)

        entry_data = coordinator.config_entry.data
        host = entry_data.get(CONF_HOST)
        if host is not None:
            web_port = entry_data.get(CONF_WEB_PORT, 80)
            scheme = "https" if web_port == 443 else "http"
            configuration_url = f"{scheme}://{host}:{web_port}"
        else:
            configuration_url = None

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.unique_id)},
            manufacturer=vendor.name if vendor else "SMA",
            name=(
                f"SMA{serial_number}"
                if serial_number is not None
                else DEVICE_NAMES[coordinator.device_type]
            ),
            model=_MODEL_NAMES.get(device_type, DEVICE_NAMES[coordinator.device_type]),
            serial_number=str(serial_number) if serial_number is not None else None,
            sw_version=str(firmware_version) if firmware_version is not None else None,
            configuration_url=configuration_url,
        )

    @property
    def device(self) -> SmaComponent:
        """Return the SMA device component polled by the coordinator."""
        return self.coordinator.device
