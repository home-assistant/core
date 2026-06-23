"""Data update coordinator for Grandstream devices."""

from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from grandstream_home_api import GDSPhoneAPI, GNSNasAPI, fetch_gds_status

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import COORDINATOR_UPDATE_INTERVAL, DOMAIN

if TYPE_CHECKING:
    from . import GrandstreamRuntimeData

_LOGGER = logging.getLogger(__name__)

type GrandstreamConfigEntry = ConfigEntry["GrandstreamRuntimeData"]


class GrandstreamCoordinator(DataUpdateCoordinator[str]):
    """Class to manage fetching data from Grandstream device."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: GrandstreamConfigEntry,
        api: GDSPhoneAPI | GNSNasAPI,
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

        assert self.config_entry is not None
        assert self.config_entry.unique_id is not None
        # Update firmware version in device registry
        device_registry = dr.async_get(self.hass)
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, self.config_entry.unique_id)}
        )
        if device:
            device_registry.async_update_device(device.id, sw_version=version)
            _LOGGER.debug("Updated firmware version to %s", version)

    async def _async_update_data(self) -> str:
        """Fetch data from API endpoint (polling)."""
        try:
            # Fetch data from device (GDS and GSC use same API)
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

        # Update firmware version (doesn't raise exceptions)
        self._update_firmware_version(result.get("version") or self._discovery_version)

        return result["phone_status"]
