"""DataUpdateCoordinator for aerosmart."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import override

from aerosmart_modbus import AerosmartDevice
from aerosmart_modbus.aerosmart import SETTINGS_COMPONENTS
from modbus_connection import ModbusError
from modbus_connection.model import UpdateReport

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type AerosmartConfigEntry = ConfigEntry[AerosmartRuntimeData]


class AerosmartCoordinator(DataUpdateCoordinator[UpdateReport]):
    """Refresh one category of aerosmart components on its own schedule."""

    config_entry: AerosmartConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: AerosmartConfigEntry,
        device: AerosmartDevice,
        poll: Callable[[], Awaitable[UpdateReport]],
        interval: timedelta,
        label: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{entry.title} {label}",
            config_entry=entry,
            update_interval=interval,
        )
        self.device = device
        self._poll = poll
        self._failed: frozenset[str] = frozenset()

    @override
    async def _async_update_data(self) -> UpdateReport:
        """Fetch one poll category and retain partial successes."""
        try:
            report = await self._poll()
        except ModbusError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        if not report.updated:
            errors = list(report.failed.values())
            failure = UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={
                    "error": str(errors[0]) if errors else "no subsystem answered"
                },
            )
            if not errors:
                raise failure
            raise failure from ExceptionGroup(
                "every aerosmart subsystem failed", errors
            )

        for name in sorted(report.failed.keys() - self._failed):
            _LOGGER.warning(
                "%s failed to refresh and is keeping its previous values: %s",
                name,
                report.failed[name],
            )
        for name in sorted(report.updated & self._failed):
            _LOGGER.info("%s is available again", name)
        self._failed = frozenset(report.failed)
        self._async_update_device_info(report)
        return report

    def _async_update_device_info(self, report: UpdateReport) -> None:
        """Update device metadata after a successful general subsystem poll."""
        if "general" not in report.updated:
            return

        registry = dr.async_get(self.hass)
        device = registry.async_get_device_by_identifier(
            (DOMAIN, self.config_entry.entry_id), self.config_entry.entry_id
        )
        if device is None:
            return

        general = self.device.general
        if (device_type := general.device_type) is not None:
            registry.async_update_device(device.id, model=str(device_type))
        if (software_version := general.software_version) is not None:
            registry.async_update_device(device.id, sw_version=str(software_version))


@dataclass
class AerosmartRuntimeData:
    """The device and its two polling coordinators."""

    device: AerosmartDevice
    readings: AerosmartCoordinator
    settings: AerosmartCoordinator

    def coordinator_for(self, component: str) -> AerosmartCoordinator:
        """Return the coordinator responsible for a component."""
        if component in SETTINGS_COMPONENTS:
            return self.settings
        return self.readings
