"""Data update coordinators for Intesis Modbus gateways."""

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import override

from intesis_gw_modbus import ErrorState, IntesisSingleUnitGateway, WrongGatewayError
from modbus_connection import ModbusError
from modbus_connection.model import UpdateReport

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
    UpdateFailedUnreachable,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=15)

type IntesisConfigEntry = ConfigEntry[IntesisData]


@dataclass(frozen=True, kw_only=True)
class IntesisData:
    """The coordinators of one config entry."""

    gateway: IntesisCoordinator
    unit: IntesisUnitCoordinator


class IntesisCoordinator(DataUpdateCoordinator[UpdateReport]):
    """Poll one gateway and hand its update report to its entities."""

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
        return report

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


class IntesisUnitCoordinator(DataUpdateCoordinator[UpdateReport]):
    """Follow the air conditioner behind a gateway.

    The gateway coordinator does the polling. This one passes its report on to
    the entities of the air conditioner, unless the gateway cannot reach it.
    """

    config_entry: IntesisConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: IntesisConfigEntry,
        gateway: IntesisCoordinator,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{entry.title} air conditioner",
        )
        self.gateway = gateway
        self.device = gateway.device

    @callback
    def async_follow_gateway(self) -> None:
        """Refresh after each poll of the gateway."""
        self.config_entry.async_create_background_task(
            self.hass, self.async_refresh(), f"{DOMAIN}_{self.name}_refresh"
        )

    @override
    async def async_request_refresh(self) -> None:
        """Ask the gateway for a poll, which this coordinator then follows."""
        await self.gateway.async_request_refresh()

    @override
    async def _async_update_data(self) -> UpdateReport:
        if not self.gateway.last_update_success:
            raise UpdateFailedUnreachable(
                translation_domain=DOMAIN, translation_key="gateway_unavailable"
            ) from self.gateway.last_exception
        error = self.device.error
        if error is not None and error.state is ErrorState.COMMUNICATION_ERROR:
            raise UpdateFailedUnreachable(
                translation_domain=DOMAIN, translation_key="unit_unreachable"
            )
        return self.gateway.data
