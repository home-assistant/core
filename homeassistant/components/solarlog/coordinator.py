"""DataUpdateCoordinator for solarlog integration."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
import logging

from solarlog_cli.solarlog_connector import SolarLogConnector
from solarlog_cli.solarlog_exceptions import (
    SolarLogAuthenticationError,
    SolarLogConnectionError,
    SolarLogUpdateError,
)
from solarlog_cli.solarlog_models import EnergyData, InverterData, SolarlogData

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import slugify

from .const import DOMAIN
from .models import SolarlogIntegrationData

_LOGGER = logging.getLogger(__name__)

type SolarlogConfigEntry = ConfigEntry[SolarlogIntegrationData]


class SolarLogBasicDataCoordinator(DataUpdateCoordinator[SolarlogData]):
    """Get and update the basic solarlog data."""

    config_entry: SolarlogConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SolarlogConfigEntry,
        api: SolarLogConnector,
    ) -> None:
        """Initialize the data object."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="SolarLog",
            update_interval=timedelta(seconds=60),
        )

        self.unique_id = config_entry.entry_id
        self.solarlog = api

    async def _async_setup(self) -> None:
        """Do initialization logic."""
        _LOGGER.debug("Start async_setup")
        logged_in = False
        if self.solarlog.password != "":
            if logged_in := await self.renew_authentication():
                await self.solarlog.test_extended_data_available()
        if logged_in or await self.solarlog.test_extended_data_available():
            device_list = await self.solarlog.update_device_list()
            self.solarlog.set_enabled_devices(dict.fromkeys(device_list, True))

    async def _async_update_data(self) -> SolarlogData:
        """Update the data from the SolarLog device."""
        _LOGGER.debug("Start basic data update")

        try:
            data = await self.solarlog.update_basic_data()
        except SolarLogConnectionError as ex:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="config_entry_not_ready",
            ) from ex
        except SolarLogAuthenticationError as ex:
            if await self.renew_authentication():
                # login was successful, update availability of extended data, retry data update
                await self.solarlog.test_extended_data_available()
                raise ConfigEntryNotReady(
                    translation_domain=DOMAIN,
                    translation_key="config_entry_not_ready",
                ) from ex
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
            ) from ex
        except SolarLogUpdateError as ex:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from ex

        _LOGGER.debug("Basic data successfully updated")

        return data

    async def renew_authentication(self) -> bool:
        """Renew access token for SolarLog API."""
        logged_in = False
        try:
            logged_in = await self.solarlog.login()
        except SolarLogAuthenticationError as ex:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
            ) from ex
        except (SolarLogConnectionError, SolarLogUpdateError) as ex:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="config_entry_not_ready",
            ) from ex

        _LOGGER.debug("Credentials successfully updated? %s", logged_in)

        return logged_in


class SolarLogDeviceDataCoordinator(DataUpdateCoordinator[dict[int, InverterData]]):
    """Get and update the device data of solarlog."""

    config_entry: SolarlogConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SolarlogConfigEntry,
        api: SolarLogConnector,
    ) -> None:
        """Initialize the data object."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="SolarLogDevices",
            update_interval=timedelta(seconds=60),
        )

        self.new_device_callbacks: list[Callable[[int], None]] = []
        self._devices_last_update: set[tuple[int, str]] = set()
        self.solarlog = api

    async def _async_update_data(self) -> dict[int, InverterData]:
        """Update the data from the SolarLog device."""
        _LOGGER.debug("Start device data update")

        try:
            await self.solarlog.update_device_list()
            inverter_data = await self.solarlog.update_inverter_data()
        except SolarLogAuthenticationError as ex:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
            ) from ex
        except (SolarLogConnectionError, SolarLogUpdateError) as ex:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from ex

        _LOGGER.debug("Device data successfully updated")

        self.data = inverter_data

        self._async_add_remove_devices(inverter_data)

        return inverter_data

    def _async_add_remove_devices(self, inverter_data: dict[int, InverterData]) -> None:
        """Add new devices, remove non-existing devices."""

        if (
            current_devices := {
                (k, self.solarlog.device_name(k)) for k in inverter_data
            }
        ) == self._devices_last_update:
            return

        # remove old devices
        if removed_devices := self._devices_last_update - current_devices:
            _LOGGER.info("Removed device(s): %s", ", ".join(map(str, removed_devices)))
            device_registry = dr.async_get(self.hass)

            for removed_device in removed_devices:
                device_name = ""
                for did, dn in self._devices_last_update:
                    if did == removed_device[0]:
                        device_name = dn
                        break
                if device := device_registry.async_get_device(
                    identifiers={
                        (
                            DOMAIN,
                            f"{self.config_entry.entry_id}_{slugify(device_name)}",
                        )
                    }
                ):
                    device_registry.async_update_device(
                        device_id=device.id,
                        remove_config_entry_id=self.config_entry.entry_id,
                    )
                    _LOGGER.info("Device removed from device registry: %s", device.id)

        # add new devices
        if new_devices := current_devices - self._devices_last_update:
            _LOGGER.info("New device(s) found: %s", ", ".join(map(str, new_devices)))
            for device_id in new_devices:
                for callback in self.new_device_callbacks:
                    callback(device_id[0])

        self._devices_last_update = current_devices


class SolarLogLongtimeDataCoordinator(DataUpdateCoordinator[EnergyData]):
    """Get and update the solarlog longtime energy data."""

    config_entry: SolarlogConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SolarlogConfigEntry,
        api: SolarLogConnector,
        timeout: float,
    ) -> None:
        """Initialize the data object."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name="SolarLogLongtimeEnergy",
            update_interval=timedelta(seconds=timeout * 2),
        )

        self.solarlog = api
        self.connection_timeout = timeout

    async def _async_update_data(self) -> EnergyData:
        """Update the energy data from the SolarLog device."""
        _LOGGER.debug(
            "Start energy data update with timeout=%s", self.connection_timeout
        )

        try:
            energy_data: EnergyData | None = await self.solarlog.update_energy_data(
                timeout=self.connection_timeout
            )
        except SolarLogAuthenticationError as ex:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="auth_failed",
            ) from ex
        except (SolarLogConnectionError, SolarLogUpdateError) as ex:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from ex

        if energy_data is None:
            energy_data = EnergyData(None, None)

        self.config_entry.runtime_data.basic_data_coordinator.data.self_consumption_year = energy_data.self_consumption

        _LOGGER.debug("Energy data successfully updated")

        return energy_data
