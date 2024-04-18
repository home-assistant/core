"""The PrusaLink integration."""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from datetime import timedelta
import logging
from time import monotonic
from typing import TypeVar

from pyprusalink import JobInfo, LegacyPrinterStatus, PrinterStatus, PrusaLink
from pyprusalink.types import InvalidAuth, PrusaLinkError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .config_flow import ConfigFlow
from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.CAMERA, Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PrusaLink from a config entry."""
    if entry.version == 1 and entry.minor_version < 2:
        raise ConfigEntryError("Please upgrade your printer's firmware.")

    api = PrusaLink(
        get_async_client(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )

    coordinators = {
        "legacy_status": LegacyStatusCoordinator(hass, api),
        "status": StatusCoordinator(hass, api),
        "job": JobUpdateCoordinator(hass, api),
    }
    for coordinator in coordinators.values():
        await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinators

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    if config_entry.version > ConfigFlow.VERSION:
        # This means the user has downgraded from a future version
        return False

    new_data = dict(config_entry.data)
    if config_entry.version == 1:
        if config_entry.minor_version < 2:
            # Add username and password
            # "maker" is currently hardcoded in the firmware
            # https://github.com/prusa3d/Prusa-Firmware-Buddy/blob/bfb0ffc745ee6546e7efdba618d0e7c0f4c909cd/lib/WUI/wui_api.h#L19
            username = "maker"
            password = config_entry.data[CONF_API_KEY]

            api = PrusaLink(
                get_async_client(hass),
                config_entry.data[CONF_HOST],
                username,
                password,
            )
            try:
                await api.get_info()
            except InvalidAuth:
                # We are unable to reach the new API which usually means
                # that the user is running an outdated firmware version
                ir.async_create_issue(
                    hass,
                    DOMAIN,
                    "firmware_5_1_required",
                    is_fixable=False,
                    severity=ir.IssueSeverity.ERROR,
                    translation_key="firmware_5_1_required",
                    translation_placeholders={
                        "entry_title": config_entry.title,
                        "prusa_mini_firmware_update": "https://help.prusa3d.com/article/firmware-updating-mini-mini_124784",
                        "prusa_mk4_xl_firmware_update": "https://help.prusa3d.com/article/how-to-update-firmware-mk4-xl_453086",
                    },
                )
                # There is a check in the async_setup_entry to prevent the setup if minor_version < 2
                # Currently we can't reload the config entry
                # if the migration returns False.
                # Return True here to workaround that.
                return True

            new_data[CONF_USERNAME] = username
            new_data[CONF_PASSWORD] = password

        ir.async_delete_issue(hass, DOMAIN, "firmware_5_1_required")
        hass.config_entries.async_update_entry(
            config_entry, data=new_data, minor_version=2
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


T = TypeVar("T", PrinterStatus, LegacyPrinterStatus, JobInfo)


class PrusaLinkUpdateCoordinator(DataUpdateCoordinator[T], ABC):  # pylint: disable=hass-enforce-coordinator-module
    """Update coordinator for the printer."""

    config_entry: ConfigEntry
    expect_change_until = 0.0

    def __init__(self, hass: HomeAssistant, api: PrusaLink) -> None:
        """Initialize the update coordinator."""
        self.api = api

        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=self._get_update_interval(None)
        )

    async def _async_update_data(self) -> T:
        """Update the data."""
        try:
            async with asyncio.timeout(5):
                data = await self._fetch_data()
        except InvalidAuth:
            raise UpdateFailed("Invalid authentication") from None
        except PrusaLinkError as err:
            raise UpdateFailed(str(err)) from err

        self.update_interval = self._get_update_interval(data)
        return data

    @abstractmethod
    async def _fetch_data(self) -> T:
        """Fetch the actual data."""
        raise NotImplementedError

    @callback
    def expect_change(self) -> None:
        """Expect a change."""
        self.expect_change_until = monotonic() + 30

    def _get_update_interval(self, data: T) -> timedelta:
        """Get new update interval."""
        if self.expect_change_until > monotonic():
            return timedelta(seconds=5)

        return timedelta(seconds=30)


class StatusCoordinator(PrusaLinkUpdateCoordinator[PrinterStatus]):  # pylint: disable=hass-enforce-coordinator-module
    """Printer update coordinator."""

    async def _fetch_data(self) -> PrinterStatus:
        """Fetch the printer data."""
        return await self.api.get_status()


class LegacyStatusCoordinator(PrusaLinkUpdateCoordinator[LegacyPrinterStatus]):  # pylint: disable=hass-enforce-coordinator-module
    """Printer legacy update coordinator."""

    async def _fetch_data(self) -> LegacyPrinterStatus:
        """Fetch the printer data."""
        return await self.api.get_legacy_printer()


class JobUpdateCoordinator(PrusaLinkUpdateCoordinator[JobInfo]):  # pylint: disable=hass-enforce-coordinator-module
    """Job update coordinator."""

    async def _fetch_data(self) -> JobInfo:
        """Fetch the printer data."""
        return await self.api.get_job()


class PrusaLinkEntity(CoordinatorEntity[PrusaLinkUpdateCoordinator]):  # pylint: disable=hass-enforce-coordinator-module
    """Defines a base PrusaLink entity."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this PrusaLink device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            name=self.coordinator.config_entry.title,
            manufacturer="Prusa",
            configuration_url=self.coordinator.api.client.host,
        )
