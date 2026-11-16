"""Data update coordinator for Intesis Modbus gateways."""

from datetime import timedelta
import logging
from typing import override

from intesis_gw_modbus import ErrorState, IntesisSingleUnitGateway, WrongGatewayError
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
        self._failing: set[str] = set()
        self.unit_unreachable = False

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
        self._log_component_changes(report)
        self._follow_temperature_format()
        self._check_unit_reachable()
        return report

    def _follow_temperature_format(self) -> None:
        """Read and write in the format the gateway's DIP switches select now.

        The format saved at setup only serves until the gateway reports a
        setpoint, which is what the format is detected from.
        """
        detected = self.device.detected_temperature_format
        if detected is None or detected is self.device.temperature_format:
            return
        _LOGGER.info(
            "%s: the gateway now reports temperatures as %s", self.name, detected
        )
        self.device.temperature_format = detected

    def _check_unit_reachable(self) -> None:
        """Note whether the gateway reaches its unit, and log when that changes."""
        error = self.device.error
        unreachable = (
            error is not None and error.state is ErrorState.COMMUNICATION_ERROR
        )
        if unreachable and not self.unit_unreachable:
            _LOGGER.info(
                "%s: the gateway cannot reach the air conditioner, "
                "which is unavailable",
                self.name,
            )
        elif self.unit_unreachable and not unreachable:
            _LOGGER.info("%s: the gateway reaches the air conditioner again", self.name)
        self.unit_unreachable = unreachable

    def _log_component_changes(self, report: UpdateReport) -> None:
        """Log a sub-system's first failure and its recovery, once each."""
        for name, cause in report.failed.items():
            if name not in self._failing:
                self._failing.add(name)
                _LOGGER.info(
                    "%s: %s failed to refresh, its entities are unavailable: %s",
                    self.name,
                    name,
                    cause,
                )
        for name in report.updated & self._failing:
            self._failing.discard(name)
            _LOGGER.info("%s: %s is available again", self.name, name)
