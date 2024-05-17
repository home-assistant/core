"""Elmax integration common classes and utilities."""

from __future__ import annotations

import ssl

from elmax_api.model.endpoint import DeviceEndpoint
from elmax_api.model.panel import PanelEntry
from packaging import version

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    ELMAX_LOCAL_API_PATH,
    MIN_APIV2_SUPPORTED_VERSION,
    SIGNAL_PANEL_UPDATE,
)
from .coordinator import ElmaxCoordinator


def get_direct_api_url(host: str, port: int, use_ssl: bool) -> str:
    """Return the direct API url given the base URI."""
    schema = "https" if use_ssl else "http"
    return f"{schema}://{host}:{port}/{ELMAX_LOCAL_API_PATH}"


def build_direct_ssl_context(cadata: str) -> ssl.SSLContext:
    """Create a custom SSL context for direct-api verification."""
    context = ssl.SSLContext(protocol=ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_verify_locations(cadata=cadata)
    return context


def check_local_version_supported(api_version: str | None) -> bool:
    """Check whether the given API version is supported."""
    if api_version is None:
        return False
    return version.parse(api_version) >= version.parse(MIN_APIV2_SUPPORTED_VERSION)


class DirectPanel(PanelEntry):
    """Helper class for wrapping a directly accessed Elmax Panel."""

    def __init__(self, panel_uri):
        """Construct the object."""
        super().__init__(panel_uri, True, {})

    def get_name_by_user(self, username: str) -> str:
        """Return the panel name."""
        return f"Direct Panel {self.hash}"


class ElmaxEntity(CoordinatorEntity[ElmaxCoordinator]):
    """Wrapper for Elmax entities."""

    _last_state: DeviceEndpoint = None

    def __init__(
        self,
        elmax_device: DeviceEndpoint,
        panel_version: str,
        coordinator: ElmaxCoordinator,
    ) -> None:
        """Construct the object."""
        super().__init__(coordinator=coordinator)
        self._device = elmax_device
        self._attr_unique_id = elmax_device.endpoint_id
        self._attr_name = elmax_device.name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.panel_entry.hash)},
            name=coordinator.panel_entry.get_name_by_user(
                coordinator.http_client.get_authenticated_username()
            ),
            manufacturer="Elmax",
            model=panel_version,
            sw_version=panel_version,
        )

    async def async_added_to_hass(self) -> None:
        """Register push notifications callbacks if available."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SIGNAL_PANEL_UPDATE}-{self.coordinator.panel_entry.hash}-{self._device.endpoint_id}",
                self._handle_update,
            )
        )
        return await super().async_added_to_hass()

    @callback
    def _handle_update(self, endpoint_status: DeviceEndpoint) -> None:
        self._last_state = endpoint_status
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.coordinator.panel_entry.online
