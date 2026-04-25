"""Coordinator for the vizio component."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any

from pyvizio import VizioAsync
from pyvizio.api.apps import AppConfig
from pyvizio.api.input import InputItem
from pyvizio.const import APPS, INPUT_APPS
from pyvizio.util import gen_apps_list_from_url

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


@dataclass(frozen=True)
class VizioRuntimeData:
    """Runtime data for Vizio integration."""

    device_coordinator: VizioDeviceCoordinator


@dataclass(frozen=True)
class VizioDeviceData:
    """Raw data fetched from Vizio device."""

    # Power state
    is_on: bool

    # Audio settings from get_all_settings("audio")
    audio_settings: dict[str, Any] | None = None

    # Sound mode options from get_setting_options("audio", "eq")
    sound_mode_list: list[str] | None = None

    # Current input from get_current_input()
    current_input: str | None = None

    # Available inputs from get_inputs_list()
    input_list: list[InputItem] | None = None

    # Current app config from get_current_app_config() (TVs only)
    current_app_config: AppConfig | None = None


class VizioDeviceCoordinator(DataUpdateCoordinator[VizioDeviceData]):
    """Coordinator for Vizio device data."""

    config_entry: VizioConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: VizioConfigEntry,
        device: VizioAsync,
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

    async def _async_setup(self) -> None:
        """Fetch device info and update device registry."""
        model = await self.device.get_model_name(log_api_exception=False)
        version = await self.device.get_version(log_api_exception=False)

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

    async def _async_update_data(self) -> VizioDeviceData:
        """Fetch all device data."""
        is_on = await self.device.get_power_state(log_api_exception=False)

        if is_on is None:
            raise UpdateFailed(
                f"Unable to connect to {self.config_entry.data[CONF_HOST]}"
            )

        if not is_on:
            return VizioDeviceData(is_on=False)

        # Device is on - fetch all data
        audio_settings = await self.device.get_all_settings(
            VIZIO_AUDIO_SETTINGS, log_api_exception=False
        )

        sound_mode_list = None
        if audio_settings and VIZIO_SOUND_MODE in audio_settings:
            sound_mode_list = await self.device.get_setting_options(
                VIZIO_AUDIO_SETTINGS, VIZIO_SOUND_MODE, log_api_exception=False
            )

        current_input = await self.device.get_current_input(log_api_exception=False)
        input_list = await self.device.get_inputs_list(log_api_exception=False)

        current_app_config = None
        # Only attempt to fetch app config if the device is a TV and supports apps
        if (
            self.config_entry.data[CONF_DEVICE_CLASS] == MediaPlayerDeviceClass.TV
            and input_list
            and any(input_item.name in INPUT_APPS for input_item in input_list)
        ):
            current_app_config = await self.device.get_current_app_config(
                log_api_exception=False
            )

        return VizioDeviceData(
            is_on=True,
            audio_settings=audio_settings,
            sound_mode_list=sound_mode_list,
            current_input=current_input,
            input_list=input_list,
            current_app_config=current_app_config,
        )


class VizioAppsDataUpdateCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
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

    async def async_setup(self) -> None:
        """Load initial data from storage and register shutdown."""
        await self.async_register_shutdown()
        self.data = await self.store.async_load() or APPS

    async def _async_update_data(self) -> list[dict[str, Any]]:
        """Update data via library."""
        if data := await gen_apps_list_from_url(
            session=async_get_clientsession(self.hass)
        ):
            # Reset the fail count and threshold when the data is successfully retrieved
            self.fail_count = 0
            self.fail_threshold = 10
            # Store the new data if it has changed so we have it for the next restart
            if data != self.data:
                await self.store.async_save(data)
            return data
        # For every failure, increase the fail count until we reach the threshold.
        # We then log a warning, increase the threshold, and reset the fail count.
        # This is here to prevent silent failures but to reduce repeat logs.
        if self.fail_count == self.fail_threshold:
            _LOGGER.warning(
                (
                    "Unable to retrieve the apps list from the external server for the "
                    "last %s days"
                ),
                self.fail_threshold,
            )
            self.fail_count = 0
            self.fail_threshold += 10
        else:
            self.fail_count += 1
        return self.data
