"""The Dremel 3D Printer (3D20, 3D40, 3D45) integration."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from dremel3dpy import Dremel3DPrinter
from requests.exceptions import ConnectTimeout, HTTPError

from homeassistant.config_entries import SOURCE_USER, ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
import homeassistant.util.dt as dt_util

from .const import _LOGGER, DOMAIN, PLATFORMS, SCAN_INTERVAL
from .services import async_setup_services


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the OctoPrint component."""
    if DOMAIN not in config:
        return True

    domain_config = config[DOMAIN]

    for conf in domain_config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_USER},
                data={
                    CONF_HOST: conf[CONF_HOST],
                },
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Dremel 3D Printer from a config entry."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    try:
        api = await hass.async_add_executor_job(
            Dremel3DPrinter, config_entry.data[CONF_HOST]
        )

    except (ConnectTimeout, HTTPError) as exc:
        raise ConfigEntryNotReady(
            f"Unable to connect to Dremel 3D Printer: {exc}"
        ) from exc
    except Exception as exc:
        raise ConfigEntryNotReady(
            f"Unknown error connecting to Dremel 3D Printer: {exc}"
        ) from exc

    coordinator = Dremel3DPrinterDataUpdateCoordinator(
        hass, f"{DOMAIN}-{config_entry.entry_id}", api, SCAN_INTERVAL.seconds
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN][config_entry.entry_id] = coordinator
    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)
    await async_setup_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Dremel config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        del hass.data[DOMAIN]

    return unload_ok


class Dremel3DPrinterDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Dremel 3D Printer data."""

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        api: Dremel3DPrinter,
        interval: int,
    ) -> None:
        """Initialize Dremel 3D Printer data update coordinator."""
        DataUpdateCoordinator.__init__(
            self,
            hass,
            _LOGGER,
            name=name,
            update_interval=timedelta(seconds=interval),
        )
        self.printer_offline = False
        self.api = api

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via APIs."""
        try:
            await self.hass.async_add_executor_job(self.api.refresh)
        except RuntimeError:
            if not self.printer_offline:
                _LOGGER.debug("Unable to refresh printer information: Printer offline")
                self.printer_offline = True
        else:
            self.printer_offline = False

        return {
            "last_read_time": dt_util.utcnow(),
        }


class Dremel3DPrinterDeviceEntity(
    CoordinatorEntity[Dremel3DPrinterDataUpdateCoordinator], Entity
):
    """Defines a Dremel 3D Printer device entity."""

    def __init__(
        self,
        coordinator: Dremel3DPrinterDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the base device entity."""
        super().__init__(coordinator)
        self._entry_id = config_entry.entry_id

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and not self.coordinator.printer_offline
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this Dremel printer."""
        api = self.coordinator.api
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            manufacturer=api.get_manufacturer(),
            model=api.get_model(),
            name=api.get_title(),
            sw_version=api.get_firmware_version(),
        )
