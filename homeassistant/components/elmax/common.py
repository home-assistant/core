"""Elmax integration common classes and utilities."""
from __future__ import annotations

from datetime import timedelta
import logging
from logging import Logger

import async_timeout
from elmax_api.exceptions import (
    ElmaxApiError,
    ElmaxBadLoginError,
    ElmaxBadPinError,
    ElmaxNetworkError,
)
from elmax_api.http import GenericElmax
from elmax_api.model.actuator import Actuator
from elmax_api.model.endpoint import DeviceEndpoint
from elmax_api.model.panel import PanelEntry, PanelStatus
from httpx import ConnectError, ConnectTimeout

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DEFAULT_TIMEOUT, DOMAIN, ELMAX_LOCAL_API_PATH

_LOGGER = logging.getLogger(__name__)


def get_direct_api_url(base_uri: str) -> str:
    """Return the direct API url given the base URI."""
    return f"{base_uri.strip('/').lower()}/{ELMAX_LOCAL_API_PATH}"


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
            return self._state_by_endpoint.get(actuator_id)
        raise HomeAssistantError("Unknown actuator")

    def get_zone_state(self, zone_id: str) -> Actuator:
        """Return state of a specific zone."""
        if self._state_by_endpoint is not None:
            return self._state_by_endpoint.get(zone_id)
        raise HomeAssistantError("Unknown zone")

    @property
    def http_client(self):
        """Return the current http client being used by this instance."""
        return self._client

    async def _async_update_data(self):
        try:
            async with async_timeout.timeout(DEFAULT_TIMEOUT):
                # The following command might fail in case of the panel is offline.
                # In this case, just print a warning and return None: listeners will assume the panel
                # offline.
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
        except (ConnectError, ConnectTimeout, ElmaxNetworkError) as err:
            raise UpdateFailed(
                "A network error occurred while communicating with Cloud/Elmax Panel."
                "If connecting against the Cloud, make sure HA can reach the internet."
                "If connecting directly to the Elmax Panel, make sure the panel is online and "
                "no firewall is blocking it."
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
        self._panel_version = panel_version
        self._client = coordinator.http_client

    @property
    def panel_id(self) -> str | None:
        """Retrieve the panel id."""
        return self.coordinator.panel_entry.hash

    @property
    def unique_id(self) -> str | None:
        """Provide a unique id for this entity."""
        return self._device.endpoint_id

    @property
    def name(self) -> str | None:
        """Return the entity name."""
        return self._device.name

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device specific attributes."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.panel_entry.hash)},
            "name": self.coordinator.panel_entry.get_name_by_user(
                self.coordinator.http_client.get_authenticated_username()
            ),
            "manufacturer": "Elmax",
            "model": self._panel_version,
            "sw_version": self._panel_version,
        }

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.coordinator.panel_entry.online
