"""Coordinator for Aqvify integration."""

from dataclasses import dataclass
from datetime import timedelta
import logging

from aiohttp import ClientResponseError
from pyaqvify import (
    AqvifyAPI,
    AqvifyAuthException,
    AqvifyDeviceData,
    AqvifyDevices,
    AqvifyHourAggregatedValues,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.dt import utcnow

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(minutes=5)
UPDATE_INTERVAL_SLOW = timedelta(minutes=30)

type AqvifyConfigEntry = ConfigEntry[AqvifyRuntimeData]


@dataclass
class AqvifyRuntimeData:
    """Runtime data for the Aqvify integration."""

    coordinator: AqvifyCoordinator
    aggr_data_coordinator: AqvifyAggrDataCoordinator


@dataclass
class AqvifyCoordinatorData:
    """Data class for storing coordinator data."""

    devices: AqvifyDevices
    device_data: dict[str, AqvifyDeviceData]


class AqvifyCoordinator(DataUpdateCoordinator[AqvifyCoordinatorData]):
    """Data update coordinator for Aqvify devices."""

    config_entry: AqvifyConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: AqvifyConfigEntry, api_client: AqvifyAPI
    ) -> None:
        """Initialize the Aqvify data update coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{DOMAIN} main",
            update_interval=UPDATE_INTERVAL,
            config_entry=entry,
        )

        self.api_client = api_client
        self.previous_devices: set[str] = set()

    async def _async_setup(self) -> None:
        """Set up the coordinator."""
        try:
            await self.api_client.async_get_account_id()
        except AqvifyAuthException:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_api_key",
            ) from None
        except ClientResponseError as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="api_error",
                translation_placeholders={
                    "entry": self.config_entry.title,
                },
            ) from err
        except TimeoutError as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="api_timeout",
                translation_placeholders={
                    "entry": self.config_entry.title,
                },
            ) from err

    async def _async_update_data(self) -> AqvifyCoordinatorData:
        """Fetch device state."""
        try:
            devices = await self.api_client.async_get_devices()
        except AqvifyAuthException:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_api_key",
            ) from None
        except ClientResponseError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="api_error",
                translation_placeholders={
                    "entry": self.config_entry.title,
                },
            ) from err
        except TimeoutError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="api_timeout",
                translation_placeholders={
                    "entry": self.config_entry.title,
                },
            ) from err

        current_devices = set(devices.devices.keys())
        if stale_devices := self.previous_devices - current_devices:
            account_id = self.config_entry.unique_id
            device_registry = dr.async_get(self.hass)
            for device_id in stale_devices:
                device = device_registry.async_get_device(
                    identifiers={(DOMAIN, f"{account_id}_{device_id}")}
                )
                if device:
                    device_registry.async_update_device(
                        device_id=device.id,
                        remove_config_entry_id=self.config_entry.entry_id,
                    )
        self.previous_devices = current_devices

        device_data = {}
        for aqvify_device in devices.devices.values():
            try:
                device_key = str(aqvify_device.device_key)
                device_data[
                    device_key
                ] = await self.api_client.async_get_device_latest_data(device_key)
            except AqvifyAuthException:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="invalid_api_key",
                ) from None
            except ClientResponseError as err:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="api_error",
                    translation_placeholders={
                        "entry": self.config_entry.title,
                    },
                ) from err
            except TimeoutError as err:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="api_timeout",
                    translation_placeholders={
                        "entry": self.config_entry.title,
                    },
                ) from err

        return AqvifyCoordinatorData(
            devices=devices,
            device_data=device_data,
        )


class AqvifyAggrDataCoordinator(DataUpdateCoordinator):
    """Data update coordinator for Aqvify aggregated data."""

    config_entry: AqvifyConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: AqvifyConfigEntry, api_client: AqvifyAPI
    ) -> None:
        """Initialize the Aqvify aggregated data update coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{DOMAIN} aggr",
            update_interval=UPDATE_INTERVAL_SLOW,
            config_entry=entry,
        )

        self.api_client = api_client

    @staticmethod
    def _get_times() -> tuple[str, str]:
        current_time = utcnow()
        beg_time = (
            (current_time - timedelta(hours=1))
            .replace(minute=0)
            .strftime("%G-%m-%dT%H:%MZ")
        )
        end_time = (
            (current_time - timedelta(hours=1))
            .replace(minute=59)
            .strftime("%G-%m-%dT%H:%MZ")
        )
        return beg_time, end_time

    async def _async_update_data(self) -> dict[str, AqvifyHourAggregatedValues]:
        """Fetch device state."""
        devices = self.config_entry.runtime_data.coordinator.data.devices

        device_data: dict[str, AqvifyHourAggregatedValues] = {}
        for device in devices.devices.values():
            try:
                device_key = str(device.device_key)
                beg_time, end_time = self._get_times()
                aggr_data = await self.api_client.async_get_hour_aggregation(
                    device_key,
                    beg_time,
                    end_time,
                )
                device_data[device_key] = aggr_data.aggr_list[0]
            except AqvifyAuthException:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="invalid_api_key",
                ) from None
            except ClientResponseError as err:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="api_error",
                    translation_placeholders={
                        "entry": self.config_entry.title,
                    },
                ) from err
            except TimeoutError as err:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="api_timeout",
                    translation_placeholders={
                        "entry": self.config_entry.title,
                    },
                ) from err

        return device_data
