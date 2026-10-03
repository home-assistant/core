"""Shared entity helpers for the energieleser integration."""

from energieleser import WaermeleserDevice

from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import DeviceInfo

from .const import CONF_SW_VERSION, DOMAIN, device_model_name
from .coordinator import EnergieleserCoordinator


def build_device_info(coordinator: EnergieleserCoordinator) -> DeviceInfo:
    """Return the device info shared by all entities of one device."""
    host = coordinator.config_entry.data[CONF_HOST]

    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.device_id)},
        name=coordinator.device_id,
        manufacturer="nineti GmbH",
        model=device_model_name(coordinator.data.device_type),
        # Only wärmeleser devices report a fabrication number; others omit it.
        serial_number=(
            coordinator.data.fabrication_number
            if isinstance(coordinator.data, WaermeleserDevice)
            else None
        ),
        sw_version=coordinator.config_entry.data.get(CONF_SW_VERSION),
        configuration_url=f"http://{host}/",
    )
