"""Shared entity model for reCamera Pro."""

from typing import override

from recamera_protocol import RecameraError, RecameraValidationError, format_url_host

from homeassistant.const import CONF_HOST
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_HW_VERSION,
    CONF_MAC_ADDRESS,
    CONF_MODEL,
    CONF_SERIAL_NUMBER,
    CONF_SW_VERSION,
    DOMAIN,
    MANUFACTURER,
)
from .coordinator import RecameraCoordinator


def recamera_device_info(coordinator: RecameraCoordinator) -> DeviceInfo:
    """Return the canonical device metadata for this camera."""
    data = coordinator.config_entry.data
    mac_address = data.get(CONF_MAC_ADDRESS)
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.device_id)},
        connections=({(CONNECTION_NETWORK_MAC, mac_address)} if mac_address else set()),
        manufacturer=MANUFACTURER,
        model=(
            coordinator.data.info.base_plate_model
            if coordinator.data is not None
            else data.get(CONF_MODEL)
        ),
        name=coordinator.config_entry.title,
        serial_number=(
            coordinator.data.info.serial_number
            if coordinator.data is not None
            else data.get(CONF_SERIAL_NUMBER)
        ),
        hw_version=(
            coordinator.data.info.hardware_version
            if coordinator.data is not None
            else data.get(CONF_HW_VERSION)
        ),
        sw_version=(
            coordinator.data.info.firmware_version
            if coordinator.data is not None
            else data.get(CONF_SW_VERSION)
        ),
        configuration_url=(f"https://{format_url_host(data[CONF_HOST])}"),
    )


def recamera_service_error(error: RecameraError) -> HomeAssistantError:
    """Map device validation and execution failures to HA action errors."""
    error_type = (
        ServiceValidationError
        if isinstance(error, RecameraValidationError)
        else HomeAssistantError
    )
    return error_type(
        str(error),
        translation_domain=DOMAIN,
        translation_key=error.translation_key,
        translation_placeholders=error.translation_placeholders,
    )


class RecameraEntity(CoordinatorEntity[RecameraCoordinator]):
    """Base entity for one reCamera Pro."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: RecameraCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_device_info = recamera_device_info(coordinator)

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return device metadata with the active connection URL."""
        info = recamera_device_info(self.coordinator)
        info["configuration_url"] = (
            f"https://{format_url_host(self.coordinator.client.host)}"
        )
        return info

    @property
    @override
    def available(self) -> bool:
        """Return whether device metadata is available."""
        return super().available
