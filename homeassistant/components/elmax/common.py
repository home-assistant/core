"""Elmax integration common classes and utilities."""

from __future__ import annotations

from asyncio import timeout
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
from elmax_api.http import Elmax, GenericElmax
from elmax_api.model.actuator import Actuator
from elmax_api.model.area import Area
from elmax_api.model.cover import Cover
from elmax_api.model.endpoint import DeviceEndpoint
from elmax_api.model.panel import PanelEntry, PanelStatus
from httpx import ConnectError, ConnectTimeout
from packaging import version

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
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


class DirectPanel(PanelEntry):
    """Helper class for wrapping a directly accessed Elmax Panel."""

    def __init__(self, panel_uri):
        """Construct the object."""
        super().__init__(panel_uri, True, {})

    def get_name_by_user(self, username: str) -> str:
        """Return the panel name."""
        return f"Direct Panel {self.hash}"


class ElmaxCoordinator(DataUpdateCoordinator[PanelStatus]):  # pylint: disable=hass-enforce-coordinator-module
    """Coordinator helper to handle Elmax API polling."""

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
        self._state_by_endpoint = None
        super().__init__(
            hass=hass, logger=logger, name=name, update_interval=update_interval
        )

    @property
    def panel_entry(self) -> PanelEntry:
        """Return the panel entry."""
        return self._panel_entry

    def get_actuator_state(self, actuator_id: str) -> Actuator:
        """Return state of a specific actuator."""
        if self._state_by_endpoint is not None:
            return self._state_by_endpoint[actuator_id]
        raise HomeAssistantError("Unknown actuator")

    def get_zone_state(self, zone_id: str) -> Actuator:
        """Return state of a specific zone."""
        if self._state_by_endpoint is not None:
            return self._state_by_endpoint[zone_id]
        raise HomeAssistantError("Unknown zone")

    def get_area_state(self, area_id: str) -> Area:
        """Return state of a specific area."""
        if self._state_by_endpoint is not None and area_id:
            return self._state_by_endpoint[area_id]
        raise HomeAssistantError("Unknown area")

    def get_cover_state(self, cover_id: str) -> Cover:
        """Return state of a specific cover."""
        if self._state_by_endpoint is not None:
            return self._state_by_endpoint[cover_id]
        raise HomeAssistantError("Unknown cover")

    @property
    def http_client(self):
        """Return the current http client being used by this instance."""
        return self._client

    @http_client.setter
    def http_client(self, client: GenericElmax):
        """Set the client library instance for Elmax API."""
        self._client = client

    async def _async_update_data(self):
        try:
            async with timeout(DEFAULT_TIMEOUT):
                # The following command might fail in case of the panel is offline.
                # We handle this case in the following exception blocks.
                status = await self._client.get_current_panel_status()

                # Store a dictionary for fast endpoint state access
                self._state_by_endpoint = {
                    k.endpoint_id: k for k in status.all_endpoints
                }
                return status

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
            if isinstance(self._client, Elmax):
                raise UpdateFailed(
                    "A communication error has occurred. "
                    "Make sure HA can reach the internet and that "
                    "your firewall allows communication with the Meross Cloud."
                ) from err

            raise UpdateFailed(
                "A communication error has occurred. "
                "Make sure the panel is online and that  "
                "your firewall allows communication with it."
            ) from err


class ElmaxEntity(CoordinatorEntity[ElmaxCoordinator]):
    """Wrapper for Elmax entities."""

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

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.coordinator.panel_entry.online
