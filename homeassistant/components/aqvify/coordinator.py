"""Coordinator for Aqvify integration."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, override

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

    @override
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

    @override
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
                device = device_registry.async_get_device_by_identifier(
                    (DOMAIN, f"{account_id}_{device_id}"),
                    self.config_entry.entry_id,
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
                device_key = aqvify_device.device_key
                if TYPE_CHECKING:
                    assert device_key is not None
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

    def async_add_devices(self, added_devices: set[str]) -> tuple[set[str], set[str]]:
        """Return newly discovered device keys and the full current device set."""

        current_devices = set(self.data.devices.devices)
        new_devices: set[str] = current_devices - added_devices
        return (new_devices, current_devices)


class AqvifyAggrDataCoordinator(
    DataUpdateCoordinator[dict[str, AqvifyHourAggregatedValues]]
):
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

    @override
    async def _async_update_data(self) -> dict[str, AqvifyHourAggregatedValues]:
        """Fetch device state."""
        devices = self.config_entry.runtime_data.coordinator.data.devices

        device_data: dict[str, AqvifyHourAggregatedValues] = {}
        base_time = utcnow() - timedelta(hours=1)
        beg_time = base_time.replace(minute=0, second=0, microsecond=0)
        end_time = base_time.replace(minute=59, second=0, microsecond=0)
        for device in devices.devices.values():
            device_key = device.device_key
            if TYPE_CHECKING:
                assert device_key is not None
            try:
                aggr_data = await self.api_client.async_get_hour_aggregation(
                    device_key,
                    beg_time,
                    end_time,
                )
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
            device_data[device_key] = (
                aggr_data.aggr_list[0] if len(aggr_data.aggr_list) else {}
            )

        return device_data
