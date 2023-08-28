"""Elmax integration common classes and utilities."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from logging import Logger

from elmax_api.exceptions import (
    ElmaxApiError,
    ElmaxBadLoginError,
    ElmaxBadPinError,
    ElmaxNetworkError,
    ElmaxPanelBusyError,
)
from elmax_api.http import Elmax
from elmax_api.model.actuator import Actuator
from elmax_api.model.area import Area
from elmax_api.model.cover import Cover
from elmax_api.model.endpoint import DeviceEndpoint
from elmax_api.model.panel import PanelEntry, PanelStatus

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DEFAULT_TIMEOUT, DOMAIN

_LOGGER = logging.getLogger(__name__)


class ElmaxCoordinator(DataUpdateCoordinator[PanelStatus]):
    """Coordinator helper to handle Elmax API polling."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: Logger,
        username: str,
        password: str,
        panel_id: str,
        panel_pin: str,
        name: str,
        update_interval: timedelta,
    ) -> None:
        """Instantiate the object."""
        self._client = Elmax(username=username, password=password)
        self._panel_id = panel_id
        self._panel_pin = panel_pin
        self._panel_entry = None
        self._state_by_endpoint = None
        super().__init__(
            hass=hass, logger=logger, name=name, update_interval=update_interval
        )

    @property
    def panel_entry(self) -> PanelEntry | None:
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

    async def _async_update_data(self):
        try:
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                # Retrieve the panel online status first
                panels = await self._client.list_control_panels()
                panel = next(
                    (panel for panel in panels if panel.hash == self._panel_id), None
                )

                # If the panel is no more available within the given. Raise config error as the user must
                # reconfigure it in order to  make it work again
                if not panel:
                    raise ConfigEntryAuthFailed(
                        f"Panel ID {self._panel_id} is no more linked to this user"
                        " account"
                    )

                self._panel_entry = panel

                # If the panel is online, proceed with fetching its state
                # and return it right away
                if panel.online:
                    status = await self._client.get_panel_status(
                        control_panel_id=panel.hash, pin=self._panel_pin
                    )  # type: PanelStatus

                    # Store a dictionary for fast endpoint state access
                    self._state_by_endpoint = {
                        k.endpoint_id: k for k in status.all_endpoints
                    }
                    return status

                # Otherwise, return None. Listeners will know that this means the device is offline
                return None

        except ElmaxBadPinError as err:
            raise ConfigEntryAuthFailed("Control panel pin was refused") from err
        except ElmaxBadLoginError as err:
            raise ConfigEntryAuthFailed("Refused username/password") from err
        except ElmaxApiError as err:
            raise UpdateFailed(f"Error communicating with ELMAX API: {err}") from err
        except ElmaxPanelBusyError as err:
            raise UpdateFailed(
                "Communication with the panel failed, as it is currently busy"
            ) from err
        except ElmaxNetworkError as err:
            raise UpdateFailed(
                "A network error occurred while communicating with Elmax cloud."
            ) from err


class ElmaxEntity(CoordinatorEntity[ElmaxCoordinator]):
    """Wrapper for Elmax entities."""

    def __init__(
        self,
        panel: PanelEntry,
        elmax_device: DeviceEndpoint,
        panel_version: str,
        coordinator: ElmaxCoordinator,
    ) -> None:
        """Construct the object."""
        super().__init__(coordinator=coordinator)
        self._panel = panel
        self._device = elmax_device
        self._panel_version = panel_version
        self._client = coordinator.http_client

    @property
    def panel_id(self) -> str:
        """Retrieve the panel id."""
        return self._panel.hash

    @property
    def unique_id(self) -> str | None:
        """Provide a unique id for this entity."""
        return self._device.endpoint_id

    @property
    def name(self) -> str | None:
        """Return the entity name."""
        return self._device.name

    @property
    def device_info(self) -> DeviceInfo:
        """Return device specific attributes."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._panel.hash)},
            name=self._panel.get_name_by_user(
                self.coordinator.http_client.get_authenticated_username()
            ),
            manufacturer="Elmax",
            model=self._panel_version,
            sw_version=self._panel_version,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self._panel.online
