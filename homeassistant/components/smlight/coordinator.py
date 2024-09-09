"""DataUpdateCoordinator for Smlight."""

from dataclasses import dataclass

from pysmlight import Api2, Info, Sensors
from pysmlight.const import Settings, SettingsProp
from pysmlight.exceptions import SmlightAuthError, SmlightConnectionError
from pysmlight.web import Firmware

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.issue_registry import IssueSeverity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, SCAN_FIRMWARE_INTERVAL, SCAN_INTERVAL


@dataclass
class SmData:
    """SMLIGHT data stored in the DataUpdateCoordinator."""

    sensors: Sensors
    info: Info


@dataclass
class SmFwData:
    """SMLIGHT firmware data stored in the FirmwareUpdateCoordinator."""

    info: Info
    esp_firmware: list[Firmware] | None
    zb_firmware: list[Firmware] | None


class SmDataUpdateCoordinator(DataUpdateCoordinator[SmData | SmFwData]):
    """Class to manage fetching SMLIGHT data."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, host: str, client: Api2) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=f"{DOMAIN}_{host}",
            update_interval=SCAN_INTERVAL,
        )

        self.client = client
        self.unique_id: str | None = None
        self.legacy_api: int = 0

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
        if isinstance(self.data, SmFwData):
            return
        prop = SettingsProp[setting.name].value
        setattr(self.data.sensors, prop, value)

        self.async_set_updated_data(self.data)

    async def _async_update_data(self) -> SmData | SmFwData:
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


class SmFirmwareUpdateCoordinator(SmDataUpdateCoordinator):
    """Class to manage fetching SMLIGHT firmware update data from cloud."""

    def __init__(self, hass: HomeAssistant, host: str, client: Api2) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, host, client)

        self.update_interval = SCAN_FIRMWARE_INTERVAL
        # only one update can run at a time (core or zibgee)
        self.in_progress = False

    async def _async_update_data(self) -> SmFwData:
        """Fetch data from the SMLIGHT device."""
        try:
            info = await self.client.get_info()

            return SmFwData(
                info=info,
                esp_firmware=await self.client.get_firmware_version(info.fw_channel),
                zb_firmware=await self.client.get_firmware_version(
                    info.fw_channel, device=info.model, mode="zigbee"
                ),
            )
        except SmlightAuthError as err:
            raise ConfigEntryAuthFailed from err

        except SmlightConnectionError as err:
            raise UpdateFailed(err) from err
