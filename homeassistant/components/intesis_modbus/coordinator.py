"""Data update coordinator for Intesis Modbus gateways."""

from datetime import timedelta
import logging
from typing import override

from intesis_gw_modbus import IntesisSingleUnitGateway, WrongGatewayError
from modbus_connection import ModbusError
from modbus_connection.model import UpdateReport

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=15)

type IntesisConfigEntry = ConfigEntry[IntesisCoordinator]


class IntesisCoordinator(DataUpdateCoordinator[UpdateReport]):
    """Poll one gateway and hand its update report to the entities."""

    config_entry: IntesisConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: IntesisConfigEntry,
        device: IntesisSingleUnitGateway,
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

    @override
    async def _async_update_data(self) -> UpdateReport:
        try:
            report: UpdateReport = await self.device.async_update()
        except WrongGatewayError as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN, translation_key="wrong_model"
            ) from err
        except ModbusError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="modbus_error"
            ) from err
        if not report.updated:
            raise UpdateFailed(
                translation_domain=DOMAIN, translation_key="no_component_answered"
            ) from ExceptionGroup(
                "every sub-system failed to refresh", list(report.failed.values())
            )
        return report
