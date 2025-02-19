"""Component to embed TP-Link smart home devices."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from kasa import AuthenticationError, Credentials, Device, KasaException
from kasa.iot import IotStrip

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class TPLinkData:
    """Data for the tplink integration."""

    parent_coordinator: TPLinkDataUpdateCoordinator
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

        # The iot HS300 allows a limited number of concurrent requests and
        # fetching the emeter information requires separate ones, so child
        # coordinators are created below in get_child_coordinator.
        self._update_children = not isinstance(device, IotStrip)

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
        self._previous_child_device_ids = {child.device_id for child in device.children}
        self.removed_child_device_ids: set[str] = set()
        self._child_coordinators: dict[str, TPLinkDataUpdateCoordinator] = {}

    async def _async_update_data(self) -> None:
        """Fetch all device and sensor data from api."""
        try:
            await self.device.update(update_children=self._update_children)
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

        await self._process_child_devices()

    async def _process_child_devices(self) -> None:
        """Process child devices and remove stale devices."""
        current_child_device_ids = {child.device_id for child in self.device.children}
        if (
            stale_device_ids := self._previous_child_device_ids
            - current_child_device_ids
        ):
            device_registry = dr.async_get(self.hass)
            for device_id in stale_device_ids:
                device = device_registry.async_get_device(
                    identifiers={(DOMAIN, device_id)}
                )
                if device:
                    device_registry.async_update_device(
                        device_id=device.id,
                        remove_config_entry_id=self.config_entry.entry_id,
                    )
                child_coordinator = self._child_coordinators.pop(device_id, None)
                if child_coordinator:
                    await child_coordinator.async_shutdown()

        self._previous_child_device_ids = current_child_device_ids
        self.removed_child_device_ids = stale_device_ids

    def get_child_coordinator(
        self,
        child: Device,
        platform_domain: str,
    ) -> TPLinkDataUpdateCoordinator:
        """Get separate child coordinator for a device or self if not needed."""
        # The iot HS300 allows a limited number of concurrent requests and fetching the
        # emeter information requires separate ones so create child coordinators here.
        # This does not happen for switches as the state is available on the
        # parent device info.
        if isinstance(self.device, IotStrip) and platform_domain != SWITCH_DOMAIN:
            if not (child_coordinator := self._child_coordinators.get(child.device_id)):
                # The child coordinators only update energy data so we can
                # set a longer update interval to avoid flooding the device
                child_coordinator = TPLinkDataUpdateCoordinator(
                    self.hass, child, timedelta(seconds=60), self.config_entry
                )
                self._child_coordinators[child.device_id] = child_coordinator
            return child_coordinator

        return self
