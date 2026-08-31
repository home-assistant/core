"""Data update coordinator for Grandstream devices."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import override

from grandstream_home_api import GDSPhoneAPI, fetch_gds_status

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import COORDINATOR_UPDATE_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type GrandstreamConfigEntry = ConfigEntry["GrandstreamRuntimeData"]


@dataclass
class GrandstreamRuntimeData:
    """Runtime data for Grandstream config entry."""

    api: GDSPhoneAPI
    coordinator: GrandstreamCoordinator
    device_info: DeviceInfo
    device_model: str
    product_model: str | None
    unique_id: str


class GrandstreamCoordinator(DataUpdateCoordinator[str]):
    """Class to manage fetching data from Grandstream device."""

    config_entry: GrandstreamConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: GrandstreamConfigEntry,
        api: GDSPhoneAPI,
        discovery_version: str | None = None,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=COORDINATOR_UPDATE_INTERVAL),
        )
        self._api = api
        self._discovery_version = discovery_version

    def _update_firmware_version(self, version: str | None) -> None:
        """Update device firmware version in device info."""
        if not version:
            return

        assert self.config_entry.unique_id is not None
        device_registry = dr.async_get(self.hass)
        device = device_registry.async_get_device_by_identifier(
            (DOMAIN, self.config_entry.unique_id), self.config_entry.entry_id
        )
        if device:
            device_registry.async_update_device(device.id, sw_version=version)
            _LOGGER.debug("Updated firmware version to %s", version)

    @override
    async def _async_update_data(self) -> str:
        """Fetch data from API endpoint (polling)."""
        try:
            result = await self.hass.async_add_executor_job(fetch_gds_status, self._api)
        except (RuntimeError, ValueError, OSError, KeyError) as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(e)},
            ) from e

        if result is None:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="no_status",
            )

        self._update_firmware_version(result.get("version") or self._discovery_version)

        return result["phone_status"]
