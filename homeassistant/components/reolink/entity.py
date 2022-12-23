"""Reolink parent entity class."""

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .host import ReolinkHost


class ReolinkCoordinatorEntity(CoordinatorEntity):
    """Parent class for Reolink Entities."""

    def __init__(self, hass, config):
        """Initialize ReolinkCoordinatorEntity."""
        self._hass = hass
        coordinator = self._hass.data[DOMAIN][config.entry_id].device_coordinator
        super().__init__(coordinator)

        self._host: ReolinkHost = self._hass.data[DOMAIN][config.entry_id].host
        self._channel = None

    @property
    def device_info(self):
        """Information about this entity/device."""
        conf_url = (
            f"https://{self._host.api.host}:{self._host.api.port}"
            if self._host.api.use_https
            else f"http://{self._host.api.host}:{self._host.api.port}"
        )

        if self._host.api.is_nvr and self._channel is not None:
            return {
                "identifiers": {(DOMAIN, f"{self._host.unique_id}_ch{self._channel}")},
                "via_device": (DOMAIN, self._host.unique_id),
                "name": self._host.api.camera_name(self._channel),
                "model": self._host.api.camera_model(self._channel),
                "manufacturer": self._host.api.manufacturer,
                "configuration_url": conf_url,
            }

        return {
            "identifiers": {(DOMAIN, self._host.unique_id)},
            "connections": {(CONNECTION_NETWORK_MAC, self._host.api.mac_address)},
            "name": self._host.api.nvr_name,
            "model": self._host.api.model,
            "manufacturer": self._host.api.manufacturer,
            "hw_version": self._host.api.hardware_version,
            "sw_version": self._host.api.sw_version,
            "configuration_url": conf_url,
        }

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._host.api.session_active
