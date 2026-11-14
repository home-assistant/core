"""Data update coordinator for Zehnder ComfoConnect PRO gateways."""

from datetime import timedelta
import logging
from typing import override

from comfoconnect_pro_modbus import ComfoConnectPro, UpdateReport
from modbus_connection import (
    GatewayPathUnavailableError,
    GatewayTargetError,
    ModbusError,
)
from propcache.api import cached_property

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, MANUFACTURER, MODEL, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

GATEWAY_ERRORS = (GatewayPathUnavailableError, GatewayTargetError)

type ComfoConnectProConfigEntry = ConfigEntry[ComfoConnectProDataUpdateCoordinator]


class ComfoConnectProDataUpdateCoordinator(DataUpdateCoordinator[UpdateReport]):
    """Poll the gateway's status, measurements and settings."""

    config_entry: ComfoConnectProConfigEntry
    device: ComfoConnectPro

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ComfoConnectProConfigEntry,
        device: ComfoConnectPro,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )
        self.device = device

    @cached_property
    def device_info(self) -> dr.DeviceInfo:
        """Return device information."""
        return dr.DeviceInfo(
            identifiers={(DOMAIN, self.config_entry.entry_id)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=self.config_entry.title,
        )

    @override
    async def _async_update_data(self) -> UpdateReport:
        try:
            report = await self.device.async_update()
        except ModbusError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="modbus_error",
            ) from err
        if report.failed and not report.updated:
            if all(isinstance(err, GATEWAY_ERRORS) for err in report.failed.values()):
                # The gateway refuses every read once it loses the unit
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="no_path_to_unit",
                )
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="no_component_answered",
            ) from ExceptionGroup(
                "all components failed to refresh", list(report.failed.values())
            )

        status = self.device.status
        if "status" in report.updated and not status.is_connected:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="no_ventilation_unit",
                translation_placeholders={"state": str(status.connection_code)},
            )

        return report
