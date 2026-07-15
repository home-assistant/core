"""Coordinator for the vizio component."""

from collections.abc import Coroutine
from dataclasses import asdict, dataclass
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any, override

from vizaio import (
    AppAvailability,
    AppConfig,
    AppRecord,
    ChargingStatus,
    InputInfo,
    SettingInfo,
    Vizio,
    VizioError,
    fetch_app_availability,
    fetch_remote_app_catalog,
    is_app_input,
)
from vizaio.apps import BUNDLED_APPS, BUNDLED_AVAILABILITY

from homeassistant.components.media_player import MediaPlayerDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_CLASS, CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, VIZIO_AUDIO_SETTINGS, VIZIO_SOUND_MODE

type VizioConfigEntry = ConfigEntry[VizioRuntimeData]

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)


async def _optional[T](coro: Coroutine[Any, Any, T]) -> T | None:
    """Return the call result, or None when the device API call fails."""
    try:
        return await coro
    except VizioError:
        return None


def _records_to_storage(records: tuple[AppRecord, ...]) -> list[dict[str, Any]]:
    """Serialize AppRecords for the store."""
    return [asdict(record) for record in records]


def _records_from_storage(
    data: list[dict[str, Any]],
) -> tuple[AppRecord, ...] | None:
    """Deserialize stored AppRecords, or None if the data is unreadable.

    Data stored by the previous pyvizio-based version has a different
    shape (uppercase config keys) and is discarded; the next daily
    refresh replaces it.
    """
    try:
        return tuple(
            AppRecord(
                name=item["name"],
                country=tuple(item["country"]),
                config=tuple(AppConfig(**config) for config in item["config"]),
                id=item["id"],
                description=item["description"],
                icon_url=item["icon_url"],
            )
            for item in data
        )
    except KeyError, TypeError:
        return None


@dataclass(frozen=True)
class VizioRuntimeData:
    """Runtime data for Vizio integration."""

    device_coordinator: VizioDeviceCoordinator


@dataclass(frozen=True)
class VizioDeviceData:
    """Raw data fetched from Vizio device."""

    # Power state
    is_on: bool

    # Audio settings from get_settings("audio")
    audio_settings: dict[str, SettingInfo] | None = None

    # Sound mode options from get_setting("audio", "eq")
    sound_mode_list: list[str] | None = None

    # Current input from get_current_input()
    current_input: str | None = None

    # Available inputs from get_inputs()
    input_list: list[InputInfo] | None = None

    # Current app config from get_current_app_config() (TVs only)
    current_app_config: AppConfig | None = None

    # Battery state (Crave speakers only)
    battery_level: int | None = None
    charging_status: ChargingStatus | None = None


class VizioDeviceCoordinator(DataUpdateCoordinator[VizioDeviceData]):
    """Coordinator for Vizio device data."""

    config_entry: VizioConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: VizioConfigEntry,
        device: Vizio,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.device = device

    @override
    async def _async_setup(self) -> None:
        """Fetch device info and update device registry."""
        model = await _optional(self.device.get_model_name())
        version = await _optional(self.device.get_version())

        if TYPE_CHECKING:
            assert self.config_entry.unique_id

        device_registry = dr.async_get(self.hass)
        device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            identifiers={(DOMAIN, self.config_entry.unique_id)},
            manufacturer="VIZIO",
            name=self.config_entry.data[CONF_NAME],
            model=model,
            sw_version=version,
        )

    @override
    async def _async_update_data(self) -> VizioDeviceData:
        """Fetch all device data."""
        try:
            is_on = await self.device.get_power_state()
        except VizioError as err:
            raise UpdateFailed(
                f"Unable to connect to {self.config_entry.data[CONF_HOST]}"
            ) from err

        if not is_on:
            return VizioDeviceData(is_on=False)

        # Device is on - fetch all data
        audio_settings = await _optional(self.device.get_settings(VIZIO_AUDIO_SETTINGS))

        sound_mode_list = None
        if audio_settings and VIZIO_SOUND_MODE in audio_settings:
            sound_mode = await _optional(
                self.device.get_setting(VIZIO_AUDIO_SETTINGS, VIZIO_SOUND_MODE)
            )
            if sound_mode:
                sound_mode_list = list(sound_mode.options)

        current_input = await _optional(self.device.get_current_input())
        input_list = await _optional(self.device.get_inputs())

        current_app_config = None
        # Only attempt to fetch app config if the device is a TV and supports apps
        if (
            self.config_entry.data[CONF_DEVICE_CLASS] == MediaPlayerDeviceClass.TV
            and input_list
            and any(is_app_input(input_item.name) for input_item in input_list)
        ):
            current_app_config = await _optional(self.device.get_current_app_config())

        battery_level = None
        charging_status = None
        if self.device.profile.has_battery:
            battery_level = await _optional(self.device.get_battery_level())
            charging_status = await _optional(self.device.get_charging_status())

        return VizioDeviceData(
            is_on=True,
            audio_settings=audio_settings,
            sound_mode_list=sound_mode_list,
            current_input=current_input,
            input_list=input_list,
            current_app_config=current_app_config,
            battery_level=battery_level,
            charging_status=charging_status,
        )


class VizioAppsDataUpdateCoordinator(DataUpdateCoordinator[tuple[AppRecord, ...]]):
    """Define an object to hold Vizio app config data."""

    def __init__(
        self,
        hass: HomeAssistant,
        store: Store[list[dict[str, Any]]],
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=None,
            name=DOMAIN,
            update_interval=timedelta(days=1),
        )
        self.fail_count = 0
        self.fail_threshold = 10
        self.store = store
        self.availability: tuple[AppAvailability, ...] = BUNDLED_AVAILABILITY

    async def async_setup(self) -> None:
        """Load initial data from storage and register shutdown."""
        await self.async_register_shutdown()
        stored = await self.store.async_load()
        self.data = (_records_from_storage(stored) if stored else None) or BUNDLED_APPS

    @override
    async def _async_update_data(self) -> tuple[AppRecord, ...]:
        """Update data via library."""
        session = async_get_clientsession(self.hass)
        # Availability complements the catalog for app-name resolution; it has
        # its own bundled fallback and is not persisted.
        self.availability = await fetch_app_availability(session)
        try:
            data = await fetch_remote_app_catalog(session)
        except VizioError:
            # For every failure, increase the fail count until we reach the threshold.
            # We then log a warning, increase the threshold, and reset the fail count.
            # This is here to prevent silent failures but to reduce repeat logs.
            if self.fail_count == self.fail_threshold:
                _LOGGER.warning(
                    (
                        "Unable to retrieve the apps list from the external server "
                        "for the last %s days"
                    ),
                    self.fail_threshold,
                )
                self.fail_count = 0
                self.fail_threshold += 10
            else:
                self.fail_count += 1
            return self.data
        # Reset the fail count and threshold when the data is successfully retrieved
        self.fail_count = 0
        self.fail_threshold = 10
        # Store the new data if it has changed so we have it for the next restart
        if data != self.data:
            await self.store.async_save(_records_to_storage(data))
        return data
