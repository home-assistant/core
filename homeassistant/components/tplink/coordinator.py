"""Component to embed TP-Link smart home devices."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from kasa import AuthenticationError, Credentials, Device, KasaException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class TPLinkData:
    """Data for the tplink integration."""

    parent_coordinator: TPLinkDataUpdateCoordinator
    children_coordinators: list[TPLinkDataUpdateCoordinator]
    camera_credentials: Credentials | None
    live_view: bool | None


type TPLinkConfigEntry = ConfigEntry[TPLinkData]

REQUEST_REFRESH_DELAY = 0.35


class TPLinkDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """DataUpdateCoordinator to gather data for a specific TPLink device."""

    config_entry: TPLinkConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        device: Device,
        update_interval: timedelta,
        config_entry: TPLinkConfigEntry,
    ) -> None:
        """Initialize DataUpdateCoordinator to gather data for specific SmartPlug."""
        self.device = device
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=device.host,
            update_interval=update_interval,
            # We don't want an immediate refresh since the device
            # takes a moment to reflect the state change
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=REQUEST_REFRESH_DELAY, immediate=False
            ),
        )

    async def _async_update_data(self) -> None:
        """Fetch all device and sensor data from api."""
        try:
            await self.device.update(update_children=False)
        except AuthenticationError as ex:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="device_authentication",
                translation_placeholders={
                    "func": "update",
                    "exc": str(ex),
                },
            ) from ex
        except KasaException as ex:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="device_error",
                translation_placeholders={
                    "func": "update",
                    "exc": str(ex),
                },
            ) from ex
