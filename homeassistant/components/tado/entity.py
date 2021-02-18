"""Base class for Tado entity."""
from homeassistant.helpers.entity import Entity

from .const import DEFAULT_NAME, DOMAIN, TADO_ZONE


class TadoDeviceEntity(Entity):
    """Base implementation for Tado device."""

    def __init__(self, device_info):
        """Initialize a Tado device."""
        super().__init__()
        self._device_info = device_info
        self.device_name = device_info["serialNo"]
        self.device_id = device_info["shortSerialNo"]

    @property
    def device_info(self):
        """Return the device_info of the device."""
        return {
            "identifiers": {(DOMAIN, self.device_id)},
            "name": self.device_name,
            "manufacturer": DEFAULT_NAME,
            "sw_version": self._device_info["currentFwVersion"],
            "model": self._device_info["deviceType"],
            "via_device": (DOMAIN, self._device_info["serialNo"]),
        }

    @property
    def should_poll(self):
        """Do not poll."""
        return False


class TadoZoneEntity(Entity):
    """Base implementation for Tado zone."""

    def __init__(self, zone_name, home_id, zone_id):
        """Initialize a Tado zone."""
        super().__init__()
        self._device_zone_id = f"{home_id}_{zone_id}"
        self.zone_name = zone_name
        self.zone_id = zone_id

    @property
    def device_info(self):
        """Return the device_info of the device."""
        return {
            "identifiers": {(DOMAIN, self._device_zone_id)},
            "name": self.zone_name,
            "manufacturer": DEFAULT_NAME,
            "model": TADO_ZONE,
        }

    @property
    def should_poll(self):
        """Do not poll."""
        return False
