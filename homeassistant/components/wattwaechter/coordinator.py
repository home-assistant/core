"""DataUpdateCoordinator for the WattWächter Plus integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from aio_wattwaechter import (
    Wattwaechter,
    WattwaechterAuthenticationError,
    WattwaechterConnectionError,
    WattwaechterNoDataError,
)
from aio_wattwaechter.models import MeterData, SystemInfo

from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import WattwaechterConfigEntry
from .const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_FW_VERSION,
    CONF_MAC,
    CONF_MODEL,
    DEFAULT_SCAN_INTERVAL,
    DEVICE_NAME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class WattwaechterData:
    """Data class for coordinator data."""

    meter: MeterData | None
    system: SystemInfo


class WattwaechterCoordinator(DataUpdateCoordinator[WattwaechterData]):
    """Coordinator for WattWächter Plus data updates."""

    config_entry: WattwaechterConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: WattwaechterConfigEntry,
        client: Wattwaechter,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        self.device_id: str = config_entry.data[CONF_DEVICE_ID]
        self.host: str = config_entry.data[CONF_HOST]
        self.model: str = config_entry.data.get(CONF_MODEL, "WW-Plus")
        self.mac: str = config_entry.data.get(CONF_MAC, "")
        self.fw_version: str = config_entry.data.get(CONF_FW_VERSION, "")
        self.device_name: str = (
            config_entry.data.get(CONF_DEVICE_NAME, "") or DEVICE_NAME
        )

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{self.device_id}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> WattwaechterData:
        """Fetch data from the WattWächter device."""
        try:
            try:
                meter_data = await self.client.meter_data()
            except WattwaechterNoDataError:
                meter_data = None

            system_info = await self.client.system_info()
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

        self.fw_version = (
            system_info.get_value("esp", "os_version") or self.fw_version
        )

        return WattwaechterData(meter=meter_data, system=system_info)
