"""Elmax integration common classes and utilities."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from logging import Logger
import ssl

from elmax_api.exceptions import (
    ElmaxApiError,
    ElmaxBadLoginError,
    ElmaxBadPinError,
    ElmaxNetworkError,
    ElmaxPanelBusyError,
)
from elmax_api.http import GenericElmax
from elmax_api.model.endpoint import DeviceEndpoint
from elmax_api.model.panel import PanelEntry, PanelStatus
from elmax_api.push.push import PushNotificationHandler
from httpx import ConnectError, ConnectTimeout
from packaging import version

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    DEFAULT_TIMEOUT,
    DOMAIN,
    ELMAX_LOCAL_API_PATH,
    MIN_APIV2_SUPPORTED_VERSION,
    SIGNAL_PANEL_UPDATE,
)

_LOGGER = logging.getLogger(__name__)


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


class DummyPanel(PanelEntry):
    """Helper class for wrapping a directly accessed Elmax Panel."""

    def __init__(self, panel_uri):
        """Construct the object."""
        super().__init__(panel_uri, True, {})

    def get_name_by_user(self, username: str) -> str:
        """Return the panel name."""
        return f"Direct Panel {self.hash}"


class ElmaxCoordinator(DataUpdateCoordinator[PanelStatus]):
    """Coordinator helper to handle Elmax API polling."""

    _state_by_endpoint: dict[str, DeviceEndpoint]

    def __init__(
        self,
        hass: HomeAssistant,
        logger: Logger,
        elmax_api_client: GenericElmax,
        panel: PanelEntry,
        name: str,
        update_interval: timedelta,
    ) -> None:
        """Instantiate the object."""
        self._client = elmax_api_client
        self._panel_entry = panel
        self._state_by_endpoint = {}
        self._push_notification_handler = None
        super().__init__(
            hass=hass, logger=logger, name=name, update_interval=update_interval
        )

    @property
    def panel_entry(self) -> PanelEntry:
        """Return the panel entry."""
        return self._panel_entry

    @property
    def http_client(self):
        """Return the current http client being used by this instance."""
        return self._client

    @http_client.setter
    def http_client(self, client: GenericElmax):
        """Set the client library instance for Elmax API."""
        self._client = client

    async def _async_update_data(self) -> PanelStatus:
        try:
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                # The following command might fail in case of the panel is offline.
                # In this case, just print a warning and return None: listeners will assume the panel
                # offline.
                status = await self._client.get_current_panel_status()

        except ElmaxBadPinError as err:
            raise ConfigEntryAuthFailed("Control panel pin was refused") from err
        except ElmaxBadLoginError as err:
            raise ConfigEntryAuthFailed("Refused username/password/pin") from err
        except ElmaxApiError as err:
            raise UpdateFailed(f"Error communicating with ELMAX API: {err}") from err
        except ElmaxPanelBusyError as err:
            raise UpdateFailed(
                "Communication with the panel failed, as it is currently busy"
            ) from err
        except (ConnectError, ConnectTimeout, ElmaxNetworkError) as err:
            raise UpdateFailed(
                "A network error occurred while communicating with Cloud/Elmax Panel."
                "If connecting against the Cloud, make sure HA can reach the internet."
                "If connecting directly to the Elmax Panel, make sure the panel is online and "
                "no firewall is blocking it."
            ) from err

        # If panel supports it and a it hasn't been registered yet, register the push notification handler
        if status.push_feature and self._push_notification_handler is None:
            self._register_push_notification_handler()

        self._fire_data_update(status)
        return status

    def _fire_data_update(self, status: PanelStatus):
        # Store a dictionary for fast endpoint state access
        self._state_by_endpoint = {k.endpoint_id: k for k in status.all_endpoints}
        # Send the event data to every single device
        for k, ep_status in self._state_by_endpoint.items():
            event_signal = f"{SIGNAL_PANEL_UPDATE}-{self.panel_entry.hash}-{k}"
            async_dispatcher_send(self.hass, event_signal, ep_status)

        self.async_set_updated_data(status)

    def _register_push_notification_handler(self):
        ws_ep = (
            f"{'wss' if self.http_client.base_url.scheme == 'https' else 'ws'}"
            f"://{self.http_client.base_url.host}"
            f":{self.http_client.base_url.port}"
            f"{self.http_client.base_url.path}/push"
        )
        self._push_notification_handler = PushNotificationHandler(
            endpoint=str(ws_ep),
            http_client=self.http_client,
            ssl_context=self.http_client.ssl_context,
        )
        self._push_notification_handler.register_push_notification_handler(
            self._push_handler
        )
        self._push_notification_handler.start(loop=self.hass.loop)

    async def _push_handler(self, status: PanelStatus) -> None:
        self._fire_data_update(status)

    async def async_shutdown(self) -> None:
        """Cancel any scheduled call, and ignore new runs."""
        if self._push_notification_handler is not None:
            self._push_notification_handler.unregister_push_notification_handler(
                self._push_handler
            )
            self._push_notification_handler.stop()
        self._push_notification_handler = None
        return await super().async_shutdown()


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
