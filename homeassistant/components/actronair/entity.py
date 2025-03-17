"""Classes representing Actron Air devices viz., Wall and Zone controller."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class ActronAirDevice(CoordinatorEntity):
    """Base class for Actron Air devices."""

    def __init__(self, coordinator, serial_number, name, model) -> None:
        """Initialize the base device."""
        super().__init__(coordinator)
        self.serial_number = serial_number
        self._attr_unique_id = f"{DOMAIN}_{serial_number}"
        self._attr_name = name

        # Register as a device in Home Assistant
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, serial_number)},
            name=name,
            manufacturer="Actron Air",
            model=model,
            # configuration_url="http://your-ac-ip"
        )


class ActronAirWallController(ActronAirDevice):
    """Represents the Actron Air Wall Controller."""

    def __init__(self, coordinator, serial_number) -> None:
        """Initialize ActronAir Wall Controller Device."""
        super().__init__(
            coordinator, serial_number, "Actron Air Wall Controller", "NEO Controller"
        )


class ActronAirZoneDevice(ActronAirDevice):
    """Represents an Actron Air Zone as a separate device."""

    def __init__(self, coordinator, wall_serial, zone_id) -> None:
        """Initialize a zone device."""
        serial_number = f"{wall_serial}_zone_{zone_id}"
        super().__init__(
            coordinator, serial_number, f"Zone {zone_id}", "Zone Controller"
        )
