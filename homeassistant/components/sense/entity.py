"""Base entities for Sense energy."""

from sense_energy import ASyncSenseable
from sense_energy.sense_api import SenseDevice

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN, MDI_ICONS
from .coordinator import SenseCoordinator


def sense_to_mdi(sense_icon: str) -> str:
    """Convert sense icon to mdi icon."""
    return f"mdi:{MDI_ICONS.get(sense_icon, 'power-plug')}"


class SenseEntity(CoordinatorEntity[SenseCoordinator]):
    """Base implementation of a Sense sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        gateway: ASyncSenseable,
        coordinator: SenseCoordinator,
        sense_monitor_id: str,
        unique_id: str,
    ) -> None:
        """Initialize the Sense sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{sense_monitor_id}-{unique_id}"
        self._gateway = gateway
        self._attr_device_info = DeviceInfo(
            name=f"Sense {sense_monitor_id}",
            identifiers={(DOMAIN, sense_monitor_id)},
            model="Sense",
            manufacturer="Sense Labs, Inc.",
            configuration_url="https://home.sense.com",
        )


class SenseDeviceEntity(CoordinatorEntity[SenseCoordinator]):
    """Base implementation of a Sense sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        device: SenseDevice,
        coordinator: SenseCoordinator,
        sense_monitor_id: str,
        unique_id: str,
    ) -> None:
        """Initialize the Sense sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{sense_monitor_id}-{unique_id}"
        self._device = device
        self._attr_icon = sense_to_mdi(device.icon)
        self._attr_device_info = DeviceInfo(
            name=device.name,
            identifiers={(DOMAIN, f"{sense_monitor_id}:{device.id}")},
            model="Sense",
            manufacturer="Sense Labs, Inc.",
            configuration_url="https://home.sense.com",
            via_device=(DOMAIN, sense_monitor_id),
        )
