"""DataUpdateCoordinator for the IONT integration."""

from typing import override

from pyiont import IontCharger, IontConnectionError, UpdateReport

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, MANUFACTURER, SCAN_INTERVAL

type IontConfigEntry = ConfigEntry[IontDataUpdateCoordinator]


class IontDataUpdateCoordinator(DataUpdateCoordinator[UpdateReport]):
    """Polls the charger over Modbus.

    A poll can come back partial: the library reads the device block, the
    settings and every connector on its own, so one connector falling silent
    does not take the others down with it. The report names what refreshed,
    which is what entities read their availability from.
    """

    config_entry: IontConfigEntry

    # The registry ID of the charger device, which the connector sub-devices
    # hang off. Set by setup once that device is registered.
    charger_device_id: str

    def __init__(
        self, hass: HomeAssistant, entry: IontConfigEntry, charger: IontCharger
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=SCAN_INTERVAL,
        )
        self.charger = charger
        self._silent: set[str] = set()
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer=MANUFACTURER,
            name=entry.title,
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

    @override
    async def _async_update_data(self) -> UpdateReport:
        """Poll the charger, reporting what answered."""
        try:
            report = await self.charger.async_update()
        except IontConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(err)},
            ) from err

        self._log_silence(report)
        return report

    def _log_silence(self, report: UpdateReport) -> None:
        """Log a sub-system falling silent once, and log its return."""
        for subsystem, error in report.failed.items():
            if subsystem not in self._silent:
                self._silent.add(subsystem)
                LOGGER.warning(
                    "%s: %s did not answer this poll and kept its previous values: %s",
                    self.name,
                    subsystem,
                    error,
                )

        for subsystem in report.updated & self._silent:
            self._silent.discard(subsystem)
            LOGGER.info("%s: %s is answering again", self.name, subsystem)
