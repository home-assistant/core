"""DataUpdateCoordinator for Smlight."""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass

from pysmlight import Api2, Info, Sensors
from pysmlight.const import Settings, SettingsProp
from pysmlight.exceptions import SmlightAuthError, SmlightConnectionError
from pysmlight.models import FirmwareList

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.issue_registry import IssueSeverity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, SCAN_FIRMWARE_INTERVAL, SCAN_INTERVAL


@dataclass(kw_only=True)
class SmlightData:
    """Coordinator data class."""

    data: SmDataUpdateCoordinator
    firmware: SmFirmwareUpdateCoordinator


@dataclass
class SmData:
    """SMLIGHT data stored in the DataUpdateCoordinator."""

    sensors: Sensors
    info: Info


@dataclass
class SmFwData:
    """SMLIGHT firmware data stored in the FirmwareUpdateCoordinator."""

    info: Info
    esp_firmware: FirmwareList
    zb_firmware: list[FirmwareList]


type SmConfigEntry = ConfigEntry[SmlightData]


class SmBaseDataUpdateCoordinator[_DataT](DataUpdateCoordinator[_DataT]):
    """Base Coordinator for SMLIGHT."""

    config_entry: SmConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: SmConfigEntry, client: Api2
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_{config_entry.data[CONF_HOST]}",
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
        self.legacy_api = info.legacy_api
        if info.legacy_api == 2:
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

    async def _async_update_data(self) -> _DataT:
        try:
            return await self._internal_update_data()
        except SmlightAuthError as err:
            raise ConfigEntryAuthFailed from err

        except SmlightConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect_device",
                translation_placeholders={"error": str(err)},
            ) from err

    @abstractmethod
    async def _internal_update_data(self) -> _DataT:
        """Update coordinator data."""


class SmDataUpdateCoordinator(SmBaseDataUpdateCoordinator[SmData]):
    """Class to manage fetching SMLIGHT sensor data."""

    def update_setting(self, setting: Settings, value: bool | int) -> None:
        """Update the sensor value from event."""

        prop = SettingsProp[setting.name].value
        setattr(self.data.sensors, prop, value)

        self.async_set_updated_data(self.data)

    async def _internal_update_data(self) -> SmData:
        """Fetch sensor data from the SMLIGHT device."""
        sensors = Sensors()
        if not self.legacy_api:
            sensors = await self.client.get_sensors()

        return SmData(
            sensors=sensors,
            info=await self.client.get_info(),
        )


class SmFirmwareUpdateCoordinator(SmBaseDataUpdateCoordinator[SmFwData]):
    """Class to manage fetching SMLIGHT firmware update data from cloud."""

    def __init__(
        self, hass: HomeAssistant, config_entry: SmConfigEntry, client: Api2
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, config_entry, client)

        self.update_interval = SCAN_FIRMWARE_INTERVAL
        # only one update can run at a time (core or zibgee)
        self.in_progress = False

    async def _internal_update_data(self) -> SmFwData:
        """Fetch data from the SMLIGHT device."""
        info = await self.client.get_info()
        assert info.radios is not None
        esp_firmware = None
        zb_firmware: list[FirmwareList] = []

        try:
            esp_firmware = await self.client.get_firmware_version(info.fw_channel)
            zb_firmware.extend(
                [
                    await self.client.get_firmware_version(
                        info.fw_channel,
                        device=info.model,
                        mode="zigbee",
                        zb_type=r.zb_type,
                        idx=idx,
                    )
                    for idx, r in enumerate(info.radios)
                ]
            )

        except SmlightConnectionError as err:
            self.async_set_update_error(err)

        return SmFwData(
            info=info,
            esp_firmware=esp_firmware,
            zb_firmware=zb_firmware,
        )
