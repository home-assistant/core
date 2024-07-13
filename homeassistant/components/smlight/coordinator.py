"""DataUpdateCoordinator for Smlight."""

from dataclasses import dataclass
import socket

from pysmlight.exceptions import SmlightAuthError, SmlightConnectionError
from pysmlight.web import Api2, Info, Sensors

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.network import is_ip_address

from .const import DOMAIN, LOGGER, SCAN_INTERVAL


@dataclass
class SmData:
    """SMLIGHT data stored in the DataUpdateCoordinator."""

    sensors: Sensors
    info: Info
    internet: bool


class SmDataUpdateCoordinator(DataUpdateCoordinator[SmData]):
    """Class to manage fetching SMLIGHT data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.config_entry: ConfigEntry
        super().__init__(
            hass,
            LOGGER,
            name=f"{DOMAIN}_{entry.data[CONF_HOST]}",
            update_interval=SCAN_INTERVAL,
        )

        self.hostname: str | None = self.get_hostname()
        self.unique_id: str | None = None

        self.client = Api2(
            host=entry.data[CONF_HOST], session=async_get_clientsession(hass)
        )

    def get_hostname(self) -> str | None:
        """Get hostname. Fallback to IP if not available."""
        if self.config_entry:
            host = str(self.config_entry.data[CONF_HOST])
            if is_ip_address(host):
                try:
                    host = socket.gethostbyaddr(host)[0]
                except socket.herror:
                    return host
            return host.split(".", maxsplit=1)[0]
        return None

    async def async_handle_setup(self) -> None:
        """Handle initial setup."""
        await self.async_maybe_auth()
        await self.async_config_entry_first_refresh()
        self.unique_id = format_mac(self.data.info.MAC)

    async def async_maybe_auth(self) -> None:
        """Authenticate if needed."""
        if await self.client.check_auth_needed():
            if (
                self.config_entry
                and self.config_entry.data.get(CONF_USERNAME)
                and self.config_entry.data.get(CONF_PASSWORD)
            ):
                try:
                    await self.client.authenticate(
                        self.config_entry.data[CONF_USERNAME],
                        self.config_entry.data[CONF_PASSWORD],
                    )
                except SmlightAuthError as err:
                    raise ConfigEntryAuthFailed from err
            else:
                raise ConfigEntryAuthFailed

    async def _async_update_data(self) -> SmData:
        """Fetch data from the SMLIGHT device."""
        try:
            return SmData(
                sensors=await self.client.get_sensors(),
                info=await self.client.get_info(),
                internet=False,
            )
        except SmlightConnectionError as err:
            raise UpdateFailed(err) from err
