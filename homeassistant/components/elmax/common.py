"""Elmax integration common classes and utilities."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
import logging
from logging import Logger
from typing import Any

import async_timeout
from elmax_api.exceptions import (
    ElmaxApiError,
    ElmaxBadLoginError,
    ElmaxBadPinError,
    ElmaxNetworkError,
)
from elmax_api.http import Elmax
from elmax_api.model.endpoint import DeviceEndpoint
from elmax_api.model.panel import PanelEntry, PanelStatus

from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DEFAULT_TIMEOUT, DOMAIN

_LOGGER = logging.getLogger(__name__)


class ElmaxCoordinator(DataUpdateCoordinator):
    """Coordinator helper to handle Elmax API polling."""

    def __init__(
        self,
        hass: HomeAssistantType,
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

    @property
    def panel_status(self) -> PanelStatus | None:
        """Return the last fetched panel status."""
        return self.data

    def get_endpoint_state(self, endpoint_id: str) -> DeviceEndpoint | None:
        """Return the last fetched status for the given endpoint-id."""
        if self._state_by_endpoint is not None:
            return self._state_by_endpoint.get(endpoint_id)
        return None

    @property
    def http_client(self):
        """Return the current http client being used by this instance."""
        return self._client

    async def _async_update_data(self):
        try:
            async with async_timeout.timeout(DEFAULT_TIMEOUT):
                # Retrieve the panel online status first
                panels = await self._client.list_control_panels()
                panels = list(filter(lambda x: x.hash == self._panel_id, panels))

                # If the panel is no more available within the given. Raise config error as the user must
                # reconfigure it in order to  make it work again
                if len(panels) < 1:
                    _LOGGER.error(
                        "Panel ID %s is no more linked to this user account",
                        self._panel_id,
                    )
                    raise ConfigEntryAuthFailed()

                panel = panels[0]
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
            _LOGGER.error("Control panel pin was refused")
            raise ConfigEntryAuthFailed from err
        except ElmaxBadLoginError as err:
            _LOGGER.error("Refused username/password")
            raise ConfigEntryAuthFailed from err
        except ElmaxApiError as err:
            raise HomeAssistantError(
                f"Error communicating with ELMAX API: {err}"
            ) from err
        except ElmaxNetworkError as err:
            raise HomeAssistantError(
                "Network error occurred while contacting ELMAX cloud"
            ) from err
        except Exception as err:
            _LOGGER.exception("Unexpected exception")
            raise HomeAssistantError("An unexpected error occurred") from err


class ElmaxEntity(Entity):
    """Wrapper for Elmax entities."""

    def __init__(
        self,
        panel: PanelEntry,
        elmax_device: DeviceEndpoint,
        panel_version: str,
        coordinator: ElmaxCoordinator,
    ) -> None:
        """Construct the object."""
        self._panel = panel
        self._device = elmax_device
        self._panel_version = panel_version
        self._coordinator = coordinator
        self._transitory_state = None

    @property
    def transitory_state(self) -> Any | None:
        """Return the transitory state for this entity."""
        return self._transitory_state

    @transitory_state.setter
    def transitory_state(self, value: Any) -> None:
        """Set the transitory state value."""
        self._transitory_state = value

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
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return extra attributes."""
        return {
            "index": self._device.index,
            "visible": self._device.visible,
        }

    @property
    def device_info(self):
        """Return device specific attributes."""
        return {
            "identifiers": {(DOMAIN, self._panel.hash)},
            "name": self._panel.get_name_by_user(
                self._coordinator.http_client.get_authenticated_username()
            ),
            "manufacturer": "Elmax",
            "model": self._panel_version,
            "sw_version": self._panel_version,
        }

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._panel.online

    def _http_data_changed(self) -> None:
        # Whenever new HTTP data is received from the coordinator we extract the stat of this
        # device and store it locally for later use
        device_state = self._coordinator.get_endpoint_state(self._device.endpoint_id)
        if self._device is None or device_state.__dict__ != self._device.__dict__:
            # If HTTP data has changed, we need to schedule a forced refresh
            self._device = device_state
            self.async_schedule_update_ha_state(force_refresh=True)

        # Reset the transitory state as we did receive a fresh state
        self._transitory_state = None

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return False

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass.

        To be extended by integrations.
        """
        self._coordinator.async_add_listener(self._http_data_changed)

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass.

        To be extended by integrations.
        """
        self._coordinator.async_remove_listener(self._http_data_changed)
