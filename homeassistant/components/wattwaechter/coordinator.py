"""DataUpdateCoordinator for the WattWächter Plus integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
import time

from aio_wattwaechter import (
    Wattwaechter,
    WattwaechterAuthenticationError,
    WattwaechterConnectionError,
    WattwaechterNoDataError,
)
from aio_wattwaechter.models import MeterData, SystemInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_FW_VERSION,
    CONF_MAC,
    CONF_MODEL,
    DEFAULT_SCAN_INTERVAL,
    DEVICE_NAME,
    DOMAIN,
    SYSTEM_INFO_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class WattwaechterData:
    """Data class for coordinator data."""

    meter: MeterData | None
    system: SystemInfo


class WattwaechterCoordinator(DataUpdateCoordinator[WattwaechterData]):
    """Coordinator for WattWächter Plus data updates."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: Wattwaechter,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        self.device_id: str = config_entry.data[CONF_DEVICE_ID]
        self.host: str = config_entry.data[CONF_HOST]
        self.model: str = config_entry.data.get(CONF_MODEL, "WW-Plus")
        self.mac: str = config_entry.data.get(CONF_MAC, "")
        self.fw_version: str = config_entry.data.get(CONF_FW_VERSION, "")
        self.device_name: str = config_entry.data.get(CONF_DEVICE_NAME, "") or DEVICE_NAME
        self.mdns_name: str = ""
        self._last_system_info: SystemInfo | None = None
        self._last_system_info_time: float = 0.0

        scan_interval = config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.device_id}",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.config_entry = config_entry

    async def _async_update_data(self) -> WattwaechterData:
        """Fetch data from the WattWächter device."""
        now = time.monotonic()
        needs_system_info = (
            self._last_system_info is None
            or now - self._last_system_info_time >= SYSTEM_INFO_INTERVAL
        )

        try:
            try:
                meter_data = await self.client.meter_data()
            except WattwaechterNoDataError:
                meter_data = None

            if needs_system_info:
                system_info = await self.client.system_info()
                self._last_system_info = system_info
                self._last_system_info_time = now
            else:
                system_info = self._last_system_info
        except WattwaechterAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        except WattwaechterConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err

        # Update firmware version and mDNS name from live data
        assert system_info is not None
        self.fw_version = system_info.get_value("esp", "os_version") or self.fw_version
        self.mdns_name = system_info.get_value("wifi", "mdns_name") or ""

        return WattwaechterData(meter=meter_data, system=system_info)
