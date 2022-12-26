"""Reolink parent entity class."""

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ReolinkData
from .const import DOMAIN


class ReolinkCoordinatorEntity(CoordinatorEntity):
    """Parent class for Reolink Entities."""

    def __init__(self, hass, config):
        """Initialize ReolinkCoordinatorEntity."""
        self._hass = hass
        entry_data: ReolinkData = self._hass.data[DOMAIN][config.entry_id]
        coordinator = entry_data.device_coordinator
        super().__init__(coordinator)

        self._host = entry_data.host
        self._channel = None

    @property
    def device_info(self):
        """Information about this entity/device."""
        http_s = "https" if self._host.api.use_https else "http"
        conf_url = f"{http_s}://{self._host.api.host}:{self._host.api.port}"

        if self._host.api.is_nvr and self._channel is not None:
            return DeviceInfo(
                identifiers={(DOMAIN, f"{self._host.unique_id}_ch{self._channel}")},
                via_device=(DOMAIN, self._host.unique_id),
                name=self._host.api.camera_name(self._channel),
                model=self._host.api.camera_model(self._channel),
                manufacturer=self._host.api.manufacturer,
                configuration_url=conf_url,
            )

        return DeviceInfo(
            identifiers={(DOMAIN, self._host.unique_id)},
            connections={(CONNECTION_NETWORK_MAC, self._host.api.mac_address)},
            name=self._host.api.nvr_name,
            model=self._host.api.model,
            manufacturer=self._host.api.manufacturer,
            hw_version=self._host.api.hardware_version,
            sw_version=self._host.api.sw_version,
            configuration_url=conf_url,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._host.api.session_active
