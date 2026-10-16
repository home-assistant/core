"""Polling, and what to do when an inverter stops answering."""

from datetime import timedelta
import logging
from typing import override

from kaco_modbus import (
    KacoInverter,
    NotAKacoInverterError,
    SunSpecMapShiftError,
    UpdateReport,
)
from modbus_connection import ModbusError
from propcache.api import cached_property

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)

type KacoConfigEntry = ConfigEntry[KacoDataUpdateCoordinator]


class KacoDataUpdateCoordinator(DataUpdateCoordinator[UpdateReport]):
    """Poll the inverter's readings, and report what actually came back."""

    config_entry: KacoConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: KacoConfigEntry,
        device: KacoInverter,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=SCAN_INTERVAL,
        )
        self.device = device

    @cached_property
    def device_info(self) -> DeviceInfo:
        """The one inverter every entity on this config entry belongs to."""
        info = self.device.info
        assert info is not None
        return DeviceInfo(
            identifiers={(DOMAIN, info.serial_number)},
            manufacturer=info.manufacturer,
            model=info.model,
            sw_version=info.firmware,
            serial_number=info.serial_number,
        )

    @override
    async def _async_update_data(self) -> UpdateReport:
        try:
            report = await self.device.async_update_readings()
        except NotAKacoInverterError as err:
            # Identity is settled on the first poll, so a swapped device
            # surfaces here. Retrying cannot make it a KACO.
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="not_a_kaco_inverter",
                translation_placeholders={"error": str(err)},
            ) from err
        except SunSpecMapShiftError as err:
            # Every bound register offset is stale; only rediscovery fixes it.
            self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="sunspec_map_moved",
                translation_placeholders={"error": str(err)},
            ) from err
        except ModbusError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": str(err)},
            ) from err

        if not report.updated:
            # A KACO after dark accepts the connection and answers nothing.
            # The library records that per component rather than raising it.
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="no_component_answered",
                translation_placeholders={"name": self.name},
            ) from ExceptionGroup(
                "every component failed to refresh", list(report.failed.values())
            )

        return report
