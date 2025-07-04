"""TuneBladeEntity base class."""
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN, NAME, VERSION

class TuneBladeEntity(CoordinatorEntity):
    """Base entity for TuneBlade devices, including master hub."""

    def __init__(self, coordinator, config_entry, device_id=None, device_name=None):
        """Initialize entity with coordinator, config entry, and optional device info."""
        super().__init__(coordinator)
        self.config_entry = config_entry
        self.device_id = device_id or "master"
        self.device_name = device_name or "Master"

    @property
    def unique_id(self):
        """Return a unique ID for this entity."""
        return f"{self.config_entry.entry_id}_{self.device_id}"

    @property
    def device_info(self):
        """Return device info for this entity."""
        return {
            "identifiers": {(DOMAIN, self.device_id)},
            "name": f"{self.device_name} {NAME}",
            "model": VERSION,
            "manufacturer": NAME,
        }

    @property
    def extra_state_attributes(self):
        """Return extra attributes for the device."""
        data = self.coordinator.data or {}
        device_data = data.get(self.device_id, {})
        # Return any available details; you can customize as needed
        return {
            "connected": device_data.get("connected"),
            "volume": device_data.get("volume"),
            "status_code": device_data.get("status_code"),
        }
