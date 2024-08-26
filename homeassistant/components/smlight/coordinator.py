"""DataUpdateCoordinator for Smlight."""

from dataclasses import dataclass

from pysmlight import Api2, Info, Sensors
from pysmlight.const import Settings, SettingsProp
from pysmlight.exceptions import SmlightAuthError, SmlightConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.issue_registry import IssueSeverity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, SCAN_INTERVAL


@dataclass
class SmData:
    """SMLIGHT data stored in the DataUpdateCoordinator."""

    sensors: Sensors
    info: Info


class SmDataUpdateCoordinator(DataUpdateCoordinator[SmData]):
    """Class to manage fetching SMLIGHT data."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, host: str) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=f"{DOMAIN}_{host}",
            update_interval=SCAN_INTERVAL,
        )

        self.unique_id: str | None = None
        self.client = Api2(host=host, session=async_get_clientsession(hass))
        self.legacy_api: int = 0

        self.config_entry.async_create_background_task(
            hass, self.client.sse.client(), "smlight-sse-client"
        )

    async def _async_setup(self) -> None:
        """Authenticate if needed during initial setup."""
        if await self.client.check_auth_needed():
            if (
                CONF_USERNAME in self.config_entry.data
                and CONF_PASSWORD in self.config_entry.data
            ):
                try:
                    await self.client.authenticate(
                        self.config_entry.data[CONF_USERNAME],
                        self.config_entry.data[CONF_PASSWORD],
                    )
                except SmlightAuthError as err:
                    raise ConfigEntryAuthFailed from err
            else:
                # Auth required but no credentials available
                raise ConfigEntryAuthFailed

        info = await self.client.get_info()
        self.unique_id = format_mac(info.MAC)

        if info.legacy_api:
            self.legacy_api = info.legacy_api
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                "unsupported_firmware",
                is_fixable=False,
                is_persistent=False,
                learn_more_url="https://smlight.tech/flasher/#SLZB-06",
                severity=IssueSeverity.ERROR,
                translation_key="unsupported_firmware",
            )

    def update_setting(self, setting: Settings, value: bool | int) -> None:
        """Update the sensor value from event."""
        prop = SettingsProp[setting.name].value
        setattr(self.data.sensors, prop, value)

        self.async_set_updated_data(self.data)

    async def _async_update_data(self) -> SmData:
        """Fetch data from the SMLIGHT device."""
        try:
            sensors = Sensors()
            if not self.legacy_api:
                sensors = await self.client.get_sensors()

            return SmData(
                sensors=sensors,
                info=await self.client.get_info(),
            )
        except SmlightAuthError as err:
            raise ConfigEntryAuthFailed from err

        except SmlightConnectionError as err:
            raise UpdateFailed(err) from err
