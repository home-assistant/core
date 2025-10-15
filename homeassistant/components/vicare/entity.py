"""Entities for the ViCare integration."""

from PyViCare.PyViCareDevice import Device as PyViCareDevice
from PyViCare.PyViCareDeviceConfig import PyViCareDeviceConfig
from PyViCare.PyViCareHeatingDevice import (
    HeatingDeviceWithComponent as PyViCareHeatingDeviceComponent,
)

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, VIESSMANN_DEVELOPER_PORTAL


class ViCareEntity(Entity):
    """Base class for ViCare entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        unique_id_suffix: str,
        device_serial: str | None,
        device_config: PyViCareDeviceConfig,
        device: PyViCareDevice,
        component: PyViCareHeatingDeviceComponent | None = None,
    ) -> None:
        """Initialize the entity."""
        gateway_serial = device_config.getConfig().serial
        device_id = device_config.getId()
        model = device_config.getModel().replace("_", " ")
        via_device_identifier: tuple[str, str] | None = None

        identifier = (
            f"{gateway_serial}_{device_serial.replace('-', '_')}"
            if device_serial is not None
            else f"{gateway_serial}_{device_id}"
        )

        if device_serial is not None and device_serial.startswith("zigbee-"):
            parts = device_serial.split("-")
            if len(parts) == 3:  # expect format zigbee-<zigbee-ieee>-<channel-id>
                via_device_identifier = (DOMAIN, f"{gateway_serial}_zigbee_{parts[1]}")

        self._api: PyViCareDevice | PyViCareHeatingDeviceComponent = (
            component if component else device
        )
        self._attr_unique_id = f"{identifier}-{unique_id_suffix}"
        if component:
            self._attr_unique_id += f"-{component.id}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            serial_number=device_serial,
            name=model,
            manufacturer="Viessmann",
            model=model,
            configuration_url=VIESSMANN_DEVELOPER_PORTAL,
            via_device=via_device_identifier,
        )
